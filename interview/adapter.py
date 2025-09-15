from pathlib import Path
import json, yaml

def load_from_interview():
    req_p = Path("specs/requirements.yaml")
    arch_p = Path("specs/arch.yaml")
    api_p = Path("specs/contracts/api.yaml")
    db_p  = Path("specs/contracts/db.yaml")
    ui_p  = Path("specs/contracts/ui.yaml")

    if not (req_p.exists() and arch_p.exists() and api_p.exists() and db_p.exists() and ui_p.exists()):
        raise FileNotFoundError("Missing interview outputs under specs/*")

    req = yaml.safe_load(req_p.read_text())
    arch = yaml.safe_load(arch_p.read_text())
    contracts = {
        "api": yaml.safe_load(api_p.read_text())["api"],
        "db":  yaml.safe_load(db_p.read_text())["db"],
        "ui":  yaml.safe_load(ui_p.read_text())["ui"],
    }
    policy   = yaml.safe_load(Path("policy/trustops.yaml").read_text()) if Path("policy/trustops.yaml").exists() else {}
    corpora  = yaml.safe_load(Path("corpora/allowlist.yaml").read_text()) if Path("corpora/allowlist.yaml").exists() else {}
    profile  = json.loads(Path("ui/presentation_profile.json").read_text()) if Path("ui/presentation_profile.json").exists() else {}

    nl = "; ".join(r["title"] for r in req.get("requirements", [])) or "High-level goal"
    state = json.loads(Path(".imu_runs/state.json").read_text()) if Path(".imu_runs/state.json").exists() else {"answers":{}}
    personas = state["answers"].get("personas", [])
    flows    = state["answers"].get("flows", [])

    seeds = {"contracts": contracts, "arch": arch, "policy": policy, "corpora": corpora, "ui": profile}
    arch_pref = arch.get("architecture") or arch.get("style")
    return nl, personas, flows, arch_pref, seeds
