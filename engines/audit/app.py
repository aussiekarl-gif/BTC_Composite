import os
import io
import requests
import time
import numpy as np
import pandas as pd
import streamlit as st

BASE = 'https://bitcoin-data.com/v1'
HEADERS = {'User-Agent':'Mozilla/5.0','Accept':'application/json'}

CANDIDATES = {
    'MVRV Z-Score (positive control)': ('mvrv-zscore', ['mvrvZScore','mvrv_zscore','zscore','mvrvZ','value']),
    'Puell Multiple': ('puell-multiple', ['puellMultiple','puell_multiple','puell','value']),
    'VDD Multiple': ('vdd-multiple', ['vddMultiple','vdd_multiple','value']),
    'STH MVRV': ('sth-mvrv', ['sthMvrv','sth_mvrv','mvrv','value']),
    'LTH MVRV': ('lth-mvrv', ['lthMvrv','lth_mvrv','mvrv','value']),
    'aSOPR': ('asopr', ['asopr','aSOPR','value']),
    '% Supply / UTXOs in Profit': ('profit-loss', ['profitLoss','profit_loss','profit','value','percent','pct']),
    'NVT Signal': ('nvts', ['nvts','nvtSignal','nvt_signal','value']),
    'Investor Price': ('investor-price', ['investorPrice','investor_price','price','value']),
}

# All candidate transforms are interpreted so HIGH = high valuation/risk.
# Investor Price becomes spot / investor price; all others use their raw metric.


def get_token():
    try:
        t = st.secrets.get('BGEOMETRICS_TOKEN','')
        if t: return str(t).strip()
    except Exception:
        pass
    return os.getenv('BGEOMETRICS_TOKEN','').strip()


def _pick(frame, aliases):
    if frame is None or frame.empty: return None
    lower = {str(c).lower(): c for c in frame.columns}
    for a in aliases:
        if a.lower() in lower: return lower[a.lower()]
    for a in aliases:
        for c in frame.columns:
            if a.lower() in str(c).lower(): return c
    # fallback: first numeric-looking non-date column
    for c in frame.columns:
        if str(c).lower() in {'d','date','day','thedate'}: continue
        s = pd.to_numeric(frame[c], errors='coerce')
        if s.notna().sum() >= max(3, int(0.5*len(frame))): return c
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_endpoint(endpoint, start_date, end_date, token):
    params={
        'startday':pd.Timestamp(start_date).strftime('%Y-%m-%d'),
        'endday':pd.Timestamp(end_date).strftime('%Y-%m-%d'),
    }
    h=HEADERS.copy()
    if token:
        # BGeometrics accepts Bearer auth; the token query parameter is also
        # documented, so send both for maximum compatibility.
        h['Authorization']=f'Bearer {token}'
        params['token']=token

    r=requests.get(f'{BASE}/{endpoint}',params=params,headers=h,timeout=45)

    if r.status_code == 429:
        remaining=r.headers.get('X-RateLimit-Remaining','0')
        reset=r.headers.get('X-RateLimit-Reset','')
        retry=r.headers.get('Retry-After','')
        msg='BGeometrics rate limit reached (HTTP 429). '
        if not token:
            msg += 'No API token was detected, so the free/IP quota is being used. '
        else:
            msg += 'A token was detected, but BGeometrics still reports that the quota is exhausted. '
        if retry:
            msg += f'Retry-After: {retry}s. '
        if reset:
            msg += f'Rate-limit reset: {reset}. '
        msg += f'Remaining reported: {remaining}.'
        raise RuntimeError(msg)

    if r.status_code in (401,403):
        raise RuntimeError(
            f'BGeometrics authentication failed (HTTP {r.status_code}). '
            'Check BGEOMETRICS_TOKEN in Streamlit Secrets.'
        )

    r.raise_for_status()
    payload=r.json()
    if isinstance(payload,dict):
        for k in ('data','results','items','values'):
            if isinstance(payload.get(k),list): payload=payload[k]; break
    if isinstance(payload,dict): payload=[payload]
    rows=[]
    if isinstance(payload,list):
        for item in payload:
            if not isinstance(item,dict): continue
            d=item.get('d') or item.get('date') or item.get('day') or item.get('theDate')
            if d is None: continue
            z=dict(item); z['date']=pd.to_datetime(d,utc=True,errors='coerce'); rows.append(z)
    if not rows: return pd.DataFrame()
    out=pd.DataFrame(rows).dropna(subset=['date']).set_index('date').sort_index()
    return out.loc[~out.index.duplicated(keep='last')]


def expanding_percentile(s, min_periods=52):
    # causal percentile: today's value ranked only against observations available up to today.
    x=pd.to_numeric(s,errors='coerce')
    vals=x.to_numpy(dtype=float)
    out=np.full(len(vals),np.nan)
    seen=[]
    for i,v in enumerate(vals):
        if np.isfinite(v): seen.append(v)
        if len(seen)>=min_periods and np.isfinite(v):
            a=np.asarray(seen,dtype=float)
            out[i]=(np.sum(a < v)+0.5*np.sum(a == v))/len(a)
    return pd.Series(out,index=s.index)


def spearman(a,b):
    z=pd.concat([pd.to_numeric(a,errors='coerce'),pd.to_numeric(b,errors='coerce')],axis=1).dropna()
    if len(z)<20: return np.nan
    return z.iloc[:,0].rank().corr(z.iloc[:,1].rank())


def residualize_candidate(candidate, base):
    z=pd.concat([candidate,base],axis=1).dropna()
    out=pd.Series(np.nan,index=candidate.index,dtype=float)
    if len(z)<30: return out
    y=z.iloc[:,0].to_numpy(float); x=z.iloc[:,1].to_numpy(float)
    X=np.column_stack([np.ones(len(x)),x])
    beta=np.linalg.lstsq(X,y,rcond=None)[0]
    out.loc[z.index]=y-X@beta
    return out


def era_name(dt):
    y=pd.Timestamp(dt).year
    if y<=2019: return '2016–2019'
    if y<=2022: return '2020–2022'
    return '2023–present'


def prepare_frozen(uploaded):
    df=pd.read_csv(uploaded)
    if 'date' not in df.columns: raise ValueError('CSV must contain date column')
    df['date']=pd.to_datetime(df['date'],utc=True,errors='coerce')
    df=df.dropna(subset=['date']).set_index('date').sort_index()
    if 'price_usd' not in df.columns: raise ValueError('CSV must contain price_usd')
    if 'risk_score' not in df.columns: raise ValueError('CSV must contain risk_score')
    # Monday samples only, one observation per ISO week. Keep exact Mondays when available.
    m=df[df.index.weekday==0].copy()
    if m.empty:
        m=df.resample('W-MON').first()
    m['price_usd']=pd.to_numeric(m['price_usd'],errors='coerce')
    m['risk_score']=pd.to_numeric(m['risk_score'],errors='coerce')
    for w in (4,12,26,52):
        m[f'fwd_{w}w']=m['price_usd'].shift(-w)/m['price_usd']-1
    m['era']=[era_name(i) for i in m.index]
    return m


st.title('BTC Broad Public Model Audit — Research Only')
st.caption('Purpose: screen public Bitcoin indicators for genuinely new information before anything is allowed near V5.9. No production logic is changed.')

with st.expander('What has already been rejected before testing', expanded=True):
    st.markdown('''
- **NUPL as a new input:** rejected as a near-duplicate of the MVRV/realized-cap family, not an independent confirmation.
- **Pi Cycle / more moving averages / Rainbow-style price bands:** rejected at screening because V5.9 already contains price-extension / long-run valuation information; adding more versions risks duplication.
- **Stock-to-Flow:** rejected because out-of-sample evidence is poor and the model is structurally dominated by the halving schedule.
- **Fear & Greed as another sizing pillar:** already tested separately; useful context, but it weakened the longer-horizon valuation ranking in our prior test.
- **ETF flows / funding / open interest:** useful short-term regime context, but the history is too short or horizon too short for a long-horizon accumulation-sizing pillar.
''')

st.subheader('1. Upload the frozen V5.9 R2 export')
uploaded=st.file_uploader('Use btc_v5_9_r2_frozen.csv',type=['csv'])
if uploaded is None:
    st.info('Upload the frozen R2 CSV. The audit will then query public on-chain candidates against the exact same dates.')
    st.stop()

try:
    base=prepare_frozen(uploaded)
except Exception as e:
    st.error(str(e)); st.stop()

start=base.index.min().date(); end=base.index.max().date()
st.write(f'Frozen sample: **{start} → {end}**, {len(base):,} Monday observations')

token=get_token()
if not token:
    st.error(
        'No BGEOMETRICS_TOKEN was detected. This audit needs 9 full-history API calls, '
        'while the unauthenticated/free quota is too small and only exposes the last 4 years. '
        'Add the same BGEOMETRICS_TOKEN used by the main app, then rerun.'
    )
    st.stop()
else:
    st.success('BGeometrics token detected. The token value is not displayed.')

if not st.button('Run public-model audit',type='primary'):
    st.stop()

progress=st.progress(0,text='Fetching candidate metrics…')
merged=base.copy()
fetch_status=[]
rate_limited=False
for i,(name,(endpoint,aliases)) in enumerate(CANDIDATES.items(),start=1):
    try:
        f=fetch_endpoint(endpoint,start,end,token)
        c=_pick(f,aliases)
        if c is None:
            fetch_status.append((name,endpoint,0,'No numeric field found'))
        else:
            s=pd.to_numeric(f[c],errors='coerce')
            # daily -> Monday as-of, never use future observations
            daily=s.sort_index().rename(name)
            left=pd.DataFrame(index=merged.index).reset_index().rename(columns={'date':'audit_date','index':'audit_date'})
            right=daily.reset_index().rename(columns={'date':'metric_date'})
            asof=pd.merge_asof(
                left.sort_values('audit_date'),right.sort_values('metric_date'),
                left_on='audit_date',right_on='metric_date',direction='backward'
            )
            merged[name]=pd.to_numeric(asof[name],errors='coerce').to_numpy()
            fetch_status.append((name,endpoint,int(merged[name].notna().sum()),'OK'))
    except Exception as e:
        msg=str(e)
        fetch_status.append((name,endpoint,0,msg[:220]))
        if '429' in msg or 'rate limit' in msg.lower():
            rate_limited=True
            # Do not burn additional quota once the provider has rejected a request.
            break
    progress.progress(i/len(CANDIDATES),text=f'Fetched {i}/{len(CANDIDATES)} candidates')
    # Gentle pacing. Advanced/Premium limits are far above this, but this avoids bursts.
    time.sleep(0.35)

if rate_limited:
    progress.empty()
    st.subheader('2. Data coverage')
    status_df=pd.DataFrame(fetch_status,columns=['Candidate','Endpoint','Monday observations','Status'])
    st.dataframe(status_df,use_container_width=True,hide_index=True)
    st.error(
        'BGeometrics has rate-limited the audit, so I stopped immediately instead of '
        'sending the remaining requests. Wait for the provider quota to reset and rerun. '
        'If this happens again with a paid token, verify that BGEOMETRICS_TOKEN is valid in '
        'this Streamlit app and check the token usage/quota in the BGeometrics portal.'
    )
    st.stop()

# Derived ratio for Investor Price: spot / investor price, higher = richer.
if 'Investor Price' in merged.columns:
    merged['Investor Price']=merged['price_usd']/pd.to_numeric(merged['Investor Price'],errors='coerce')

st.subheader('2. Data coverage')
status_df=pd.DataFrame(fetch_status,columns=['Candidate','Endpoint','Monday observations','Status'])
st.dataframe(status_df,use_container_width=True,hide_index=True)

horizons=(4,12,26,52)
rows=[]; era_rows=[]
for name in CANDIDATES:
    if name not in merged.columns: continue
    raw=pd.to_numeric(merged[name],errors='coerce')
    risk=expanding_percentile(raw,min_periods=52)
    base_r=pd.to_numeric(merged['risk_score'],errors='coerce')
    resid=residualize_candidate(risk,base_r)
    redundancy=spearman(risk,base_r)
    row={'Candidate':name,'Coverage':int(raw.notna().sum()),'Redundancy vs R2':redundancy}
    stable_eras=0
    for h in horizons:
        row[f'{h}w candidate']=spearman(risk,merged[f'fwd_{h}w'])
        row[f'{h}w residual']=spearman(resid,merged[f'fwd_{h}w'])
    for era in ('2016–2019','2020–2022','2023–present'):
        mask=merged['era'].eq(era)
        v=spearman(risk[mask],merged.loc[mask,'fwd_26w'])
        era_rows.append({'Candidate':name,'Era':era,'26w Spearman':v})
        if np.isfinite(v) and v<0: stable_eras+=1
    row['Negative 26w eras']=stable_eras
    # conservative screen: negative 26/52 candidate, at least one negative 26/52 residual, and >=2 eras negative
    c26=row['26w candidate']; c52=row['52w candidate']; r26=row['26w residual']; r52=row['52w residual']
    passes=(np.isfinite(c26) and c26<0 and np.isfinite(c52) and c52<0 and
            ((np.isfinite(r26) and r26<0) or (np.isfinite(r52) and r52<0)) and stable_eras>=2)
    row['Screen']=('PASS TO NEXT TEST' if passes else 'NO PROMOTION')
    rows.append(row)

res=pd.DataFrame(rows)
# rank by 26/52 residual average (more negative is better)
if not res.empty:
    res['Residual avg 26/52']=res[['26w residual','52w residual']].mean(axis=1)
    res=res.sort_values(['Screen','Residual avg 26/52'],ascending=[True,True])

st.subheader('3. Main screening results')
st.caption('Spearman interpretation: for a risk/valuation metric, more negative is better because higher risk should precede lower future returns. “Residual” asks whether the candidate still contains information after removing its linear relationship with frozen R2.')
show_cols=['Candidate','Coverage','Redundancy vs R2','4w candidate','12w candidate','26w candidate','52w candidate','26w residual','52w residual','Negative 26w eras','Screen']
if res.empty:
    st.warning('No candidate produced enough usable observations to calculate screening results.')
else:
    existing=[c for c in show_cols if c in res.columns]
    fmt={c:'{:+.3f}' for c in existing if c not in {'Candidate','Coverage','Negative 26w eras','Screen'}}
    st.dataframe(res[existing].style.format(fmt),use_container_width=True,hide_index=True)

st.subheader('4. Era stability — 26 week horizon')
era_df=pd.DataFrame(era_rows)
if not era_df.empty:
    pivot=era_df.pivot(index='Candidate',columns='Era',values='26w Spearman').reset_index()
    st.dataframe(pivot.style.format({c:'{:+.3f}' for c in pivot.columns if c!='Candidate'}),use_container_width=True,hide_index=True)

st.subheader('5. Research verdict')
if res.empty:
    st.error('No candidates had enough usable data.')
else:
    passed=res[res['Screen'].eq('PASS TO NEXT TEST')]
    if passed.empty:
        st.success('No public candidate cleared the conservative information screen. That is a useful result: keep V5.9 simple.')
    else:
        st.warning('These candidates earned only a NEXT TEST, not production inclusion:')
        st.dataframe(passed[['Candidate','Redundancy vs R2','26w candidate','52w candidate','26w residual','52w residual','Negative 26w eras']],use_container_width=True,hide_index=True)
        st.info('Next stage is equal-capital causal DCA testing with fixed, pre-declared weights and holdout eras. Nothing is promoted automatically.')

out=merged.copy(); out.index.name='date'
combined=out.reset_index().to_csv(index=False).encode()
st.download_button('Download merged audit dataset',combined,'btc_public_model_audit_merged.csv','text/csv')
summary=res.to_csv(index=False).encode()
st.download_button('Download audit summary',summary,'btc_public_model_audit_summary.csv','text/csv')

st.caption('Research only. This tool deliberately screens for redundancy before testing performance so we do not turn the DCA app into an indicator collection.')
