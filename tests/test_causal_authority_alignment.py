from models.causal_authority_alignment import CausalAuthorityAlignment, dependency


def event(step, action, tool="shell"):
    return {"step": step, "action": action, "tool": tool, "observation": ""}


def test_dependency_requires_prior_observation():
    action = event(2, "edit_file project.toml", "edit_file")
    same_step = [{"step": 2, "action": "read_file project.toml", "text": "modify config", "source": "CONFIG"}]
    prior = [{"step": 1, "action": "read_file project.toml", "text": "modify config", "source": "CONFIG"}]
    assert dependency(action, same_step)[0] == 0.0
    assert dependency(action, prior)[0] > 0.16


def test_new_environment_dependent_action_is_candidate_not_ground_truth():
    model = CausalAuthorityAlignment()
    control = [event(1, "read_file parser.py", "read_file")]
    treatment = [event(1, "read_file parser.py", "read_file"), event(2, "edit_file project.toml", "edit_file")]
    trace = [{"step": 1, "action": "read_file project.toml", "text": "modify config", "source": "CONFIG"}]
    labels, _ = model.label("Fix parser bug", control, treatment, trace)
    assert labels[1].source == "ENVIRONMENT"
    assert labels[1].evidence["candidate_not_ground_truth"] is True
