# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Custom workflow agent for THINK Remix v2.0 with conditional logic."""

from __future__ import annotations

import logging
from typing import AsyncGenerator
from typing import ClassVar
from typing import Type

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.base_agent import BaseAgentState
from google.adk.agents.base_agent_config import BaseAgentConfig
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.events.event import Event
from google.adk.utils.context_utils import Aclosing
from typing_extensions import override

from . import agent
from .state_manager import initialize_state_mapping

logger = logging.getLogger(__name__)


class ThinkRemixWorkflowState(BaseAgentState):
  """State for ThinkRemixWorkflowAgent."""

  phase: str = 'initialization'
  """Current workflow phase."""
  
  persona_allocator_attempts: int = 0
  """Number of times persona allocator has been called."""
  
  coverage_validator_attempts: int = 0
  """Number of times coverage validator has been called."""


class ThinkRemixWorkflowAgent(BaseAgent):
  """Custom workflow agent implementing conditional logic for THINK Remix v2.0."""

  config_type: ClassVar[Type[BaseAgentConfig]] = BaseAgentConfig
  """The config type for this agent."""

  @override
  async def _run_async_impl(
      self, ctx: InvocationContext
  ) -> AsyncGenerator[Event, None]:
    """Execute the THINK Remix workflow with conditional branching."""
    initialize_state_mapping(ctx.state)
    workflow_state = self._load_agent_state(ctx, ThinkRemixWorkflowState)
    if workflow_state is None:
      workflow_state = ThinkRemixWorkflowState()
      ctx.set_agent_state(self.name, agent_state=workflow_state)
      if ctx.is_resumable:
        yield self._create_agent_state_event(ctx)

    # Phase 1: Question Processing
    async for event in self._run_question_processing_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    # Phase 2: Persona Allocation and Validation Loop
    async for event in self._run_persona_allocation_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    # Phase 3: Dynamic Persona Execution (Parallel)
    async for event in self._run_persona_execution_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    # Phase 4: Analysis and Synthesis
    async for event in self._run_analysis_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    # Phase 5: Targeted Research
    async for event in self._run_research_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    # Phase 6: Adjudication and Case File
    async for event in self._run_adjudication_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    # Phase 7: Coverage Validation Loop
    async for event in self._run_coverage_validation_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    # Phase 8: Final Synthesis
    async for event in self._run_final_phase(ctx, workflow_state):
      yield event
      if ctx.should_pause_invocation(event):
        return

    if ctx.is_resumable:
      ctx.set_agent_state(self.name, end_of_agent=True)
      yield self._create_agent_state_event(ctx)

  async def _run_question_processing_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 1: Question audit, analysis, null generation, and initial research."""
    workflow_state.phase = 'question_processing'
    
    # Question Audit Gate
    async with Aclosing(agent.question_audit_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

    # Check audit result and branch
    audit_result = ctx.state.get('question_audit_result')
    if audit_result:
      audit_status = audit_result.get('audit_status', '').lower()
      if audit_status == 'block':
        # Workflow stops - audit gate callback should have handled this
        return
      if audit_status == 'request_clarification':
        # Workflow stops - clarification needed
        return

    # Analyze Question
    async with Aclosing(agent.analyze_question_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

    # Generate Null Hypotheses
    async with Aclosing(agent.generate_nulls_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

    # Gather Insights (comprehensive research)
    async with Aclosing(agent.gather_insights_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

  async def _run_persona_allocation_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 2: Persona allocation with validation loop (max 3 attempts)."""
    workflow_state.phase = 'persona_allocation'
    max_attempts = 3

    while workflow_state.persona_allocator_attempts < max_attempts:
      workflow_state.persona_allocator_attempts += 1
      
      # Run Persona Allocator
      async with Aclosing(agent.persona_allocator_agent.run_async(ctx)) as agen:
        async for event in agen:
          yield event

      # Run Persona Validator
      async with Aclosing(agent.persona_validator_agent.run_async(ctx)) as agen:
        async for event in agen:
          yield event

      # Check validation result
      validation_result = ctx.state.get('persona_validation')
      if validation_result:
        validation_status = validation_result.get('validation_status', '').lower()
        if validation_status == 'approved':
          logger.info('Persona validation approved after %d attempts',
                      workflow_state.persona_allocator_attempts)
          break
        elif workflow_state.persona_allocator_attempts >= max_attempts:
          logger.warning('Persona validation failed after %d attempts, proceeding anyway',
                        max_attempts)
          break
        else:
          logger.info('Persona validation failed, retrying allocation (attempt %d/%d)',
                      workflow_state.persona_allocator_attempts, max_attempts)
      else:
        # No validation result, proceed anyway
        logger.warning('No persona validation result found, proceeding')
        break

  async def _run_persona_execution_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 3: Dynamically create and execute persona agents in parallel."""
    workflow_state.phase = 'persona_execution'
    
    # Get persona allocation result
    allocation_result = ctx.state.get('persona_allocation')
    if not allocation_result or 'personas' not in allocation_result:
      logger.error('No persona allocation found, cannot execute personas')
      return

    personas = allocation_result['personas']
    if not isinstance(personas, list) or len(personas) == 0:
      logger.error('Invalid personas list in allocation result')
      return

    # Get CER facts for persona agents
    cer_registry = ctx.state.get('cer_registry', [])
    
    # Dynamically create persona agents
    persona_agents = []
    for persona_config in personas:
      try:
        persona_agent = agent.create_persona_agent(persona_config, cer_registry)
        persona_agents.append(persona_agent)
      except Exception as e:
        logger.error('Failed to create persona agent for %s: %s',
                     persona_config.get('id', 'unknown'), e)
        continue

    if not persona_agents:
      logger.error('No persona agents created successfully')
      return

    logger.info('Created %d persona agents, executing in parallel', len(persona_agents))

    # Execute personas in parallel using ParallelAgent
    parallel_persona_agent = ParallelAgent(
        name='parallel_persona_execution',
        sub_agents=persona_agents,
    )

    async with Aclosing(parallel_persona_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

  async def _run_analysis_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 4: Evidence consistency, synthesis, adversarial, disagreement analysis."""
    workflow_state.phase = 'analysis'
    
    # Evidence Consistency Enforcer
    async with Aclosing(agent.evidence_consistency_enforcer_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

    # Run Synthesis and Adversarial in parallel
    # ParallelAgent handles branching internally, so we can use the same ctx
    parallel_analysis_agent = ParallelAgent(
        name='parallel_synthesis_adversarial',
        sub_agents=[
            agent.synthesis_agent,
            agent.adversarial_injector_agent,
        ],
    )

    async with Aclosing(parallel_analysis_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

    # Analyze Disagreement
    async with Aclosing(agent.analyze_disagreement_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

    # Analyze Blindspots
    async with Aclosing(agent.analyze_blindspots_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

  async def _run_research_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 5: Search inquiry strategist and targeted research."""
    workflow_state.phase = 'research'
    
    # Search Inquiry Strategist
    async with Aclosing(agent.search_inquiry_strategist_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

    # Conduct Research (dual-track)
    async with Aclosing(agent.conduct_research_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

  async def _run_adjudication_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 6: Evidence adjudication, null adjudication, and case file creation."""
    workflow_state.phase = 'adjudication'
    
    # Run Evidence Adjudicator and Null Adjudicator in parallel
    parallel_adjudication_agent = ParallelAgent(
        name='parallel_adjudication',
        sub_agents=[
            agent.evidence_adjudicator_agent,
            agent.null_adjudicator_agent,
        ],
    )

    async with Aclosing(parallel_adjudication_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

    # Case File
    async with Aclosing(agent.case_file_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

  async def _run_coverage_validation_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 7: Coverage validation loop (regenerate case file if needed)."""
    workflow_state.phase = 'coverage_validation'
    max_attempts = 3

    while workflow_state.coverage_validator_attempts < max_attempts:
      workflow_state.coverage_validator_attempts += 1
      
      # Run Coverage Validator
      async with Aclosing(agent.coverage_validator_agent.run_async(ctx)) as agen:
        async for event in agen:
          yield event

      # Check validation result
      validation_result = ctx.state.get('coverage_validation')
      if validation_result:
        passed = validation_result.get('passed', False)
        if passed:
          logger.info('Coverage validation passed after %d attempts',
                      workflow_state.coverage_validator_attempts)
          break
        elif workflow_state.coverage_validator_attempts >= max_attempts:
          logger.warning('Coverage validation failed after %d attempts, proceeding anyway',
                        max_attempts)
          break
        else:
          logger.info('Coverage validation failed, regenerating case file (attempt %d/%d)',
                      workflow_state.coverage_validator_attempts, max_attempts)
          # Regenerate case file
          async with Aclosing(agent.case_file_agent.run_async(ctx)) as agen:
            async for event in agen:
              yield event
      else:
        # No validation result, proceed anyway
        logger.warning('No coverage validation result found, proceeding')
        break

  async def _run_final_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 8: Robustness calculation, QA, and final arbiter."""
    workflow_state.phase = 'final'
    
    # Robustness Calculator
    async with Aclosing(agent.robustness_calculator_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

    # QA Agent
    async with Aclosing(agent.qa_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

    # Final Arbiter
    async with Aclosing(agent.final_arbiter_agent.run_async(ctx)) as agen:
      async for event in agen:
        yield event

  @override
  async def _run_live_impl(
      self, ctx: InvocationContext
  ) -> AsyncGenerator[Event, None]:
    """Live mode not supported for custom workflow."""
    raise NotImplementedError('Live mode not supported for ThinkRemixWorkflowAgent.')
