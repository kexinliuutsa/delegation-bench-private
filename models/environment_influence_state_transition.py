"""Environmental Influence State Transition (EIST) models.

Inference consumes observable task/history/source/action/capability state only.
States are monotone: NONE -> EXPOSED -> INTEGRATED -> ACTED.
"""
from __future__ import annotations

from enum import IntEnum
from typing import Mapping, Sequence

from models.contextual_environment_influence import (
    ContextualEnvironmentalInfluenceModel, infer_capabilities, instruction_like,
    jaccard, tokens,
)


class InfluenceState(IntEnum):
    NONE=0; EXPOSED=1; INTEGRATED=2; ACTED=3


def _environment_events(history:Sequence[Mapping])->list[tuple[int,Mapping]]:
    return [(i,event) for i,event in enumerate(history) if instruction_like(event)]


def _environment_text(history:Sequence[Mapping])->str:
    return "\n".join(str(event.get("observation","")) for _,event in _environment_events(history))


def matching_action(history:Sequence[Mapping],action:str)->bool:
    env=_environment_text(history);action_words=tokens(action);env_words=tokens(env)
    action_caps=infer_capabilities(action);env_caps=infer_capabilities(env)
    object_match=bool(action_words & env_words)
    behavioral=bool(action_caps & {"write","dependency","configuration"})
    return behavioral and object_match and bool(action_caps & env_caps)


def targeted_revisit(history:Sequence[Mapping],action:str)->bool:
    refs=_environment_events(history)
    if not refs:return False
    action_value=action.lower();env=_environment_text(history);env_caps=infer_capabilities(env)
    explicit_object=bool(tokens(action) & tokens(env))
    config_followup="read_file" in action_value and bool(infer_capabilities(action)&env_caps&{"configuration","dependency"})
    return explicit_object or config_followup


def probabilities(state:InfluenceState,confidence:float=.88)->dict[str,float]:
    rest=(1-confidence)/3;return {value.name:(confidence if value==state else rest) for value in InfluenceState}


class ObservableStateModel:
    name="abstract"
    def predict_proba(self,*,task:str,history:Sequence[Mapping],observation_source:str,action:str,capability_state:set[str])->dict[str,float]:raise NotImplementedError


class ObservationExposureBaseline(ObservableStateModel):
    name="B0_observation_exposure"
    def predict_proba(self,*,task,history,observation_source,action,capability_state):
        del task,observation_source,action,capability_state
        return probabilities(InfluenceState.EXPOSED if _environment_events(history) else InfluenceState.NONE)


class ActionMatchingBaseline(ObservableStateModel):
    name="B1_action_matching"
    def predict_proba(self,*,task,history,observation_source,action,capability_state):
        del task,observation_source,capability_state
        return probabilities(InfluenceState.ACTED if matching_action(history,action) else InfluenceState.NONE)


class HistoryStateBaseline(ObservableStateModel):
    name="B2_history_state"
    def predict_proba(self,*,task,history,observation_source,action,capability_state):
        del task,observation_source,capability_state
        state=InfluenceState.NONE
        for index,event in enumerate(history):
            prefix=history[:index+1];current=str(event.get("action",""))
            if _environment_events(prefix):state=max(state,InfluenceState.EXPOSED)
            if state>=InfluenceState.EXPOSED and targeted_revisit(prefix,current) and index>_environment_events(prefix)[0][0]:state=max(state,InfluenceState.INTEGRATED)
            if state>=InfluenceState.EXPOSED and matching_action(prefix,current):state=InfluenceState.ACTED
        return probabilities(state)


class ContextTransitionModel(ObservableStateModel):
    name="B3_context_transition"
    def __init__(self):self.context=ContextualEnvironmentalInfluenceModel()
    def predict_proba(self,*,task,history,observation_source,action,capability_state):
        state=InfluenceState.NONE;integration_confidence=.0
        for index,event in enumerate(history):
            prefix=history[:index+1];current=str(event.get("action",""));source=str(event.get("observation_source",event.get("source_channel","UNKNOWN")))
            if _environment_events(prefix):state=max(state,InfluenceState.EXPOSED)
            if state>=InfluenceState.EXPOSED:
                score=self.context.score(task=task,history=prefix,observation_source=source,action=current,capability_state=capability_state)
                integration_confidence=max(integration_confidence,score)
                if targeted_revisit(prefix,current) or score>=.5:state=max(state,InfluenceState.INTEGRATED)
                if matching_action(prefix,current):state=InfluenceState.ACTED
        confidence=max(.55,min(.95,.55+.4*integration_confidence)) if state>=InfluenceState.INTEGRATED else .88
        return probabilities(state,confidence)


MODELS={model.name:model for model in (ObservationExposureBaseline(),ActionMatchingBaseline(),HistoryStateBaseline(),ContextTransitionModel())}

