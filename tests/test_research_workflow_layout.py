"""Fail closed when a Research GitHub workflow is malformed or runs history on every push.

Regression guard added after a workflow-trigger conversion temporarily produced
an invalid YAML file. This check reads configuration only: no network or broker.
"""
from pathlib import Path
import re
import unittest
import yaml

WORKFLOWS=Path(".github/workflows")
HEAVY=("research_causal_history.yml","research_200wma_quick.yml")
FAST="research_200wma_fast_safety.yml"
PAPER="research_forward_paper_200wma.yml"

class WorkflowLayoutTests(unittest.TestCase):
    def parse(self,path):
        document=yaml.load(path.read_text(),Loader=yaml.BaseLoader)
        self.assertIsInstance(document,dict,str(path))
        self.assertIsInstance(document.get("on"),dict,str(path))
        self.assertIsInstance(document.get("jobs"),dict,str(path))
        self.assertTrue(document["jobs"],str(path))
        return document

    def test_every_workflow_is_valid_yaml(self):
        files=sorted(WORKFLOWS.glob("*.yml"))
        self.assertGreater(len(files),5)
        for path in files:
            with self.subTest(path=str(path)):
                self.parse(path)

    def test_historical_experiments_are_explicitly_requested_only(self):
        request_files={
            "research_causal_history.yml":"research_runs/REQUEST_FULL_HISTORICAL.txt",
            "research_200wma_quick.yml":"research_runs/REQUEST_EXTENDED_SENSITIVITY.txt",
        }
        for filename,request_path in request_files.items():
            wf=self.parse(WORKFLOWS/filename)
            self.assertIn("workflow_dispatch",wf["on"])
            self.assertNotIn("schedule",wf["on"],filename)
            self.assertEqual(wf["on"]["push"]["branches"],
                             ["research/cycle-strategy-optimization"])
            self.assertEqual(wf["on"]["push"]["paths"],[request_path])
            self.assertTrue(Path(request_path).is_file())

    def test_fast_safety_runs_on_research_code_change(self):
        wf=self.parse(WORKFLOWS/FAST)
        self.assertIn("push",wf["on"])
        self.assertEqual(wf["on"]["push"]["branches"],["research/cycle-strategy-optimization"])
        self.assertIn("workflow_dispatch",wf["on"])
        self.assertEqual(wf.get("permissions",{}).get("contents"),"read")

    def test_paper_journal_keeps_research_only_write_gate(self):
        wf=self.parse(WORKFLOWS/PAPER)
        self.assertIn("concurrency",wf)
        self.assertIn("workflow_dispatch",wf["on"])
        steps=next(iter(wf["jobs"].values()))["steps"]
        shell="\n".join(str(s.get("run","")) for s in steps)
        self.assertIn("research/cycle-strategy-optimization",shell)

    def test_active_python_modules_exist(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            wf=self.parse(path)
            for job in wf["jobs"].values():
                for step in job.get("steps",[]):
                    for module in re.findall(r"python(?:3)? -m (engines\.research\.[\w\.]+)",str(step.get("run",""))):
                        target=Path(module.replace(".","/")+".py")
                        self.assertTrue(target.is_file(),f"{path}: missing {target}")

if __name__=="__main__":
    unittest.main()
