"""Prompt templates per module."""

from foresight_x.prompts.evaluator import evaluator_prompt
from foresight_x.prompts.future_simulator import future_simulator_prompt
from foresight_x.prompts.irrationality import irrationality_prompt
from foresight_x.prompts.option_generator import option_generator_prompt
from foresight_x.prompts.perception import perception_prompt
from foresight_x.prompts.recommender import recommender_prompt
from foresight_x.prompts.reflector import reflector_prompt

__all__ = [
    "perception_prompt",
    "irrationality_prompt",
    "option_generator_prompt",
    "future_simulator_prompt",
    "evaluator_prompt",
    "recommender_prompt",
    "reflector_prompt",
]
