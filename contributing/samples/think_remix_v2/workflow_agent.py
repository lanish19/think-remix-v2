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
from typing import Optional
from typing import Type

import json

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.base_agent import BaseAgentState
from google.adk.agents.base_agent_config import BaseAgentConfig
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.events.event import Event
from google.adk.utils.context_utils import Aclosing
from google.genai import types
from typing_extensions import override

from . import agent
from .config_loader import get_config
from .state_compat import ensure_state_mapping_methods
from .state_manager import initialize_state_mapping
from .validation import validate_agent_output_by_key

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
  
  def __init__(self, *args, **kwargs):
    """Initialize workflow agent with configuration."""
    super().__init__(*args, **kwargs)
    self._config = get_config()
  
  @property
  def max_validation_retries(self) -> int:
    """Maximum number of retries for validation failures."""
    return self._config.max_schema_validation_retries

  async def _run_agent_with_validation(
      self,
      agent_instance: BaseAgent,
      ctx: InvocationContext,
      max_retries: Optional[int] = None,
  ) -> AsyncGenerator[Event, None]:
    """Runs an agent and validates its output with retry logic.
    
    Args:
      agent_instance: The agent to run.
      ctx: Invocation context.
      max_retries: Maximum retry attempts (defaults to self.max_validation_retries).
    
    Yields:
      Events from agent execution.
    """
    if max_retries is None:
      max_retries = self.max_validation_retries
    
    retry_count = 0
    output_key = getattr(agent_instance, 'output_key', None)
    
    while retry_count <= max_retries:
      # Collect text output from events
      collected_text = []
      
      # Run the agent
      async with Aclosing(agent_instance.run_async(ctx)) as agen:
        async for event in agen:
          yield event
          # Collect text from event using ADK's event.text property
          try:
            event_text = event.text
            if event_text:
              collected_text.append(event_text)
          except (AttributeError, Exception):
            # Fallback: try to extract from content if text property not available
            pass
      
      # If no output key, skip validation
      if not output_key:
        break
      
      # Try to get output from state first (ADK stores it there)
      agent_output = ctx.session.state.get(output_key)
      output_text = None
      
      if agent_output is not None:
        # Convert state output to string
        if isinstance(agent_output, dict):
          output_text = json.dumps(agent_output)
        elif isinstance(agent_output, str):
          output_text = agent_output
        else:
          output_text = str(agent_output)
      elif collected_text:
        # Fallback to collected text from events
        output_text = '\n'.join(collected_text)
      else:
        logger.warning('No output found for key %s from agent %s (checked state and events)',
                      output_key, agent_instance.name)
        break
      
      # Validate output
      validation_result = validate_agent_output_by_key(
          output_text,
          output_key,
          agent_instance.name,
      )
      
      if validation_result.valid:
        logger.debug('Validation passed for agent %s', agent_instance.name)
        break
      
      # Validation failed
      if retry_count < max_retries:
        retry_count += 1
        logger.warning(
            'Validation failed for agent %s (attempt %d/%d): %s. Retrying...',
            agent_instance.name,
            retry_count,
            max_retries + 1,
            validation_result.error,
        )
        # Add validation error to context for agent to see
        error_context = (
            f'VALIDATION ERROR: Your previous output failed schema validation. '
            f'Error details: {validation_result.error}. '
            'Please ensure your output matches the required JSON schema exactly. '
            'Output ONLY valid JSON matching the schema - no markdown, no preamble, no commentary.'
        )
        # Store error in state so agent can access it
        ctx.session.state[f'{output_key}_validation_error'] = error_context
        # Add validation error to the conversation so agent sees it on retry
        # The agent will see this in its conversation history
        if hasattr(ctx, 'session') and ctx.session:
          try:
            error_event = Event(
                author='system',
                content=types.Content(
                    parts=[types.Part.from_text(error_context)]
                ),
            )
            ctx.session.append_event(error_event)
          except (AttributeError, TypeError) as e:
            # If we can't add to session, at least log it
            logger.debug('Could not add validation error to session: %s', e)
      else:
        logger.error(
            'Validation failed for agent %s after %d attempts: %s. Continuing anyway.',
            agent_instance.name,
            max_retries + 1,
            validation_result.error,
        )
        break

  @override
  async def _run_async_impl(
      self, ctx: InvocationContext
  ) -> AsyncGenerator[Event, None]:
    """Execute the THINK Remix workflow with conditional branching."""
    logger.info('Starting THINK Remix v2.0 workflow')
    
    # Ensure state compatibility shim is applied to the live instance
    ensure_state_mapping_methods(ctx.session.state)
    
    # Debug: Log ADK State module path to verify correct version is loaded
    try:
      import google.adk.sessions.state as state_module
      logger.debug('ADK State module path: %s', getattr(state_module, '__file__', 'unknown'))
    except Exception as e:
      logger.debug('Could not determine ADK State module path: %s', e)
    
    # Initialize state with error handling
    try:
      initialize_state_mapping(ctx.session.state)
      # Use to_dict() to safely get keys for logging
      try:
        if hasattr(ctx.session.state, 'to_dict') and callable(getattr(ctx.session.state, 'to_dict', None)):
          state_dict = ctx.session.state.to_dict()
          if isinstance(state_dict, dict):
            logger.debug('State initialized successfully. Keys: %s', list(state_dict.keys()))
          else:
            logger.debug('State initialized successfully (to_dict() returned non-dict: %s)', type(state_dict))
        elif isinstance(ctx.session.state, dict):
          logger.debug('State initialized successfully. Keys: %s', list(ctx.session.state.keys()))
        else:
          logger.debug('State initialized successfully (could not list keys - state is not dict-like)')
      except (AttributeError, TypeError) as e:
        logger.debug('State initialized successfully (could not list keys: %s)', e)
    except Exception as e:
      logger.error('Failed to initialize state: %s', e, exc_info=True)
      raise
    
    workflow_state = self._load_agent_state(ctx, ThinkRemixWorkflowState)
    if workflow_state is None:
      workflow_state = ThinkRemixWorkflowState()
      ctx.set_agent_state(self.name, agent_state=workflow_state)
      if ctx.is_resumable:
        yield self._create_agent_state_event(ctx)
    
    logger.info('Workflow state loaded: phase=%s', workflow_state.phase)

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
    logger.info('>>> Starting Phase 3: Persona Execution')
    try:
      async for event in self._run_persona_execution_phase(ctx, workflow_state):
        yield event
        if ctx.should_pause_invocation(event):
          logger.warning('Workflow paused during Phase 3')
          return
      logger.info('>>> Phase 3: Persona Execution COMPLETE')
    except Exception as e:
      logger.error('Phase 3 failed with error: %s', e, exc_info=True)
      logger.warning('Continuing to Phase 4 despite Phase 3 error')

    # Phase 4: Analysis and Synthesis
    logger.info('>>> Starting Phase 4: Analysis and Synthesis')
    try:
      async for event in self._run_analysis_phase(ctx, workflow_state):
        yield event
        if ctx.should_pause_invocation(event):
          logger.warning('Workflow paused during Phase 4')
          return
      logger.info('>>> Phase 4: Analysis and Synthesis COMPLETE')
    except Exception as e:
      logger.error('Phase 4 failed with error: %s', e, exc_info=True)
      logger.warning('Continuing to Phase 5 despite Phase 4 error')

    # Phase 5: Targeted Research
    logger.info('>>> Starting Phase 5: Targeted Research')
    try:
      async for event in self._run_research_phase(ctx, workflow_state):
        yield event
        if ctx.should_pause_invocation(event):
          logger.warning('Workflow paused during Phase 5')
          return
      logger.info('>>> Phase 5: Targeted Research COMPLETE')
    except Exception as e:
      logger.error('Phase 5 failed with error: %s', e, exc_info=True)
      logger.warning('Continuing to Phase 6 despite Phase 5 error')

    # Phase 6: Adjudication and Case File
    logger.info('>>> Starting Phase 6: Adjudication and Case File')
    try:
      async for event in self._run_adjudication_phase(ctx, workflow_state):
        yield event
        if ctx.should_pause_invocation(event):
          logger.warning('Workflow paused during Phase 6')
          return
      logger.info('>>> Phase 6: Adjudication and Case File COMPLETE')
    except Exception as e:
      logger.error('Phase 6 failed with error: %s', e, exc_info=True)
      logger.warning('Continuing to Phase 7 despite Phase 6 error')

    # Phase 7: Coverage Validation Loop
    logger.info('>>> Starting Phase 7: Coverage Validation')
    try:
      async for event in self._run_coverage_validation_phase(ctx, workflow_state):
        yield event
        if ctx.should_pause_invocation(event):
          logger.warning('Workflow paused during Phase 7')
          return
      logger.info('>>> Phase 7: Coverage Validation COMPLETE')
    except Exception as e:
      logger.error('Phase 7 failed with error: %s', e, exc_info=True)
      logger.warning('Continuing to Phase 8 despite Phase 7 error')

    # Phase 8: Final Synthesis
    logger.info('>>> Starting Phase 8: Final Synthesis')
    try:
      async for event in self._run_final_phase(ctx, workflow_state):
        yield event
        if ctx.should_pause_invocation(event):
          logger.warning('Workflow paused during Phase 8')
          return
      logger.info('>>> Phase 8: Final Synthesis COMPLETE')
    except Exception as e:
      logger.error('Phase 8 failed with error: %s', e, exc_info=True)
      logger.warning('Workflow completed with errors in Phase 8')
    
    logger.info('=== THINK Remix v2.0 Workflow COMPLETE ===')

    if ctx.is_resumable:
      ctx.set_agent_state(self.name, end_of_agent=True)
      yield self._create_agent_state_event(ctx)

  async def _run_question_processing_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 1: Question audit, analysis, null generation, and initial research."""
    logger.info('=== Phase 1: Question Processing ===')
    workflow_state.phase = 'question_processing'
    
    # Question Audit Gate
    async for event in self._run_agent_with_validation(
        agent.question_audit_agent, ctx
    ):
      yield event

    # Check audit result and branch
    audit_result = ctx.session.state.get('question_audit_result')
    if audit_result and isinstance(audit_result, dict):
      audit_status = audit_result.get('audit_status', '').lower()
      if audit_status == 'block':
        # Workflow stops - audit gate callback should have handled this
        return
      if audit_status == 'request_clarification':
        # Workflow stops - clarification needed
        return

    # Analyze Question
    async for event in self._run_agent_with_validation(
        agent.analyze_question_agent, ctx
    ):
      yield event

    # Generate Null Hypotheses
    async for event in self._run_agent_with_validation(
        agent.generate_nulls_agent, ctx
    ):
      yield event

    # Gather Insights (comprehensive research)
    async for event in self._run_agent_with_validation(
        agent.gather_insights_agent, ctx
    ):
      yield event
    
    # Validate CER facts were registered
    cer_registry = ctx.session.state.get('cer_registry', [])
    logger.info('After gather_insights: CER registry contains %d facts', len(cer_registry))
    if len(cer_registry) == 0:
      logger.warning('No CER facts registered during gather_insights phase!')

  async def _run_persona_allocation_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 2: Persona allocation with validation loop."""
    logger.info('=== Phase 2: Persona Allocation ===')
    workflow_state.phase = 'persona_allocation'
    max_attempts = self._config.max_persona_validator_attempts

    while workflow_state.persona_allocator_attempts < max_attempts:
      workflow_state.persona_allocator_attempts += 1
      
      # Run Persona Allocator
      async for event in self._run_agent_with_validation(
          agent.persona_allocator_agent, ctx
      ):
        yield event

      # Run Persona Validator
      async for event in self._run_agent_with_validation(
          agent.persona_validator_agent, ctx
      ):
        yield event

      # Check validation result
      validation_result = ctx.session.state.get('persona_validation')
      if validation_result and isinstance(validation_result, dict):
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
    logger.info('=== Phase 3: Persona Execution ===')
    workflow_state.phase = 'persona_execution'
    
    # Get persona allocation result
    allocation_result = ctx.session.state.get('persona_allocation')
    if not allocation_result or not isinstance(allocation_result, dict) or 'personas' not in allocation_result:
      logger.error('No persona allocation found, cannot execute personas')
      logger.warning('Workflow will continue but Phase 4 agents may fail without persona analyses')
      return

    personas = allocation_result['personas']
    if not isinstance(personas, list) or len(personas) == 0:
      logger.error('Invalid personas list in allocation result')
      logger.warning('Workflow will continue but Phase 4 agents may fail without persona analyses')
      return

    # Get CER facts for persona agents
    cer_registry = ctx.session.state.get('cer_registry', [])
    logger.info('Phase 3: Using %d CER facts for persona agents', len(cer_registry))
    
    # Dynamically create persona agents
    persona_agents = []
    for persona_config in personas:
      try:
        persona_agent = agent.create_persona_agent(persona_config, cer_registry)
        persona_agents.append(persona_agent)
        logger.debug('Created persona agent: %s', persona_config.get('id', 'unknown'))
      except Exception as e:
        logger.error('Failed to create persona agent for %s: %s',
                     persona_config.get('id', 'unknown'), e, exc_info=True)
        continue

    if not persona_agents:
      logger.error('No persona agents created successfully')
      logger.warning('Workflow will continue but Phase 4 agents may fail without persona analyses')
      return

    logger.info('Created %d persona agents, executing in parallel', len(persona_agents))

    # Execute personas in parallel using ParallelAgent
    try:
      parallel_persona_agent = ParallelAgent(
          name='parallel_persona_execution',
          sub_agents=persona_agents,
      )

      async with Aclosing(parallel_persona_agent.run_async(ctx)) as agen:
        async for event in agen:
          yield event
    except Exception as e:
      logger.error('Error executing persona agents in parallel: %s', e, exc_info=True)
      logger.warning('Workflow will continue but Phase 4 agents may fail without persona analyses')
      # Don't return - let workflow continue
    
    # Validate persona analyses were recorded
    persona_analyses = ctx.session.state.get('persona_analyses', [])
    logger.info('After persona execution: %d persona analyses recorded', len(persona_analyses))
    if len(persona_analyses) == 0:
      logger.warning('No persona analyses recorded! Expected %d analyses', len(persona_agents))
    
    # Also check for persona analysis output keys in state
    for persona_config in personas:
      persona_id = persona_config.get('id')
      output_key = f'persona_analysis_{persona_id}'
      if output_key in ctx.session.state:
        logger.debug('Found persona analysis in state: %s', output_key)
      else:
        logger.warning('Missing persona analysis in state: %s', output_key)

  async def _run_analysis_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 4: Evidence consistency, synthesis, adversarial, disagreement analysis."""
    logger.info('=== Phase 4: Analysis and Synthesis ===')
    workflow_state.phase = 'analysis'
    
    # Check if persona analyses exist (required for synthesis/adversarial)
    persona_analyses = ctx.session.state.get('persona_analyses', [])
    logger.info('Phase 4: Found %d persona analyses in state', len(persona_analyses))
    
    if len(persona_analyses) == 0:
      logger.warning(
          'No persona analyses found! Phase 3 may have failed. '
          'Checking for persona analysis output keys in state...'
      )
      # Check for persona analysis output keys
      allocation_result = ctx.session.state.get('persona_allocation', {})
      personas = allocation_result.get('personas', [])
      found_outputs = 0
      for persona_config in personas:
        persona_id = persona_config.get('id')
        if persona_id:
          output_key = f'persona_analysis_{persona_id}'
          if output_key in ctx.session.state:
            found_outputs += 1
            logger.info('Found persona analysis output key: %s', output_key)
      if found_outputs == 0:
        logger.error(
            'No persona analyses found in any format! '
            'Synthesis and adversarial agents may fail. Continuing anyway...'
        )
    
    # Evidence Consistency Enforcer
    try:
      async for event in self._run_agent_with_validation(
          agent.evidence_consistency_enforcer_agent, ctx
      ):
        yield event
    except Exception as e:
      logger.error('Error in evidence_consistency_enforcer: %s', e, exc_info=True)
      # Continue workflow even if this fails

    # Run Synthesis and Adversarial in parallel
    # ParallelAgent handles branching internally, so we can use the same ctx
    # Note: Validation happens after parallel execution completes
    try:
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
    except Exception as e:
      logger.error('Error in parallel synthesis/adversarial execution: %s', e, exc_info=True)
      # Continue workflow even if parallel execution fails
    
    # Validate parallel agent outputs
    for sub_agent in [agent.synthesis_agent, agent.adversarial_injector_agent]:
      output_key = getattr(sub_agent, 'output_key', None)
      if output_key:
        output = ctx.session.state.get(output_key)
        if output:
          if isinstance(output, dict):
            output_text = json.dumps(output)
          elif isinstance(output, str):
            output_text = output
          else:
            output_text = str(output)
          validation_result = validate_agent_output_by_key(
              output_text, output_key, sub_agent.name
          )
          if not validation_result.valid:
            logger.warning('Validation failed for parallel agent %s: %s',
                          sub_agent.name, validation_result.error)
        else:
          logger.debug('No output found in state for parallel agent %s (key: %s)',
                      sub_agent.name, output_key)

    # Analyze Disagreement
    try:
      async for event in self._run_agent_with_validation(
          agent.analyze_disagreement_agent, ctx
      ):
        yield event
    except Exception as e:
      logger.error('Error in analyze_disagreement: %s', e, exc_info=True)
      # Continue workflow even if this fails

    # Analyze Blindspots
    try:
      async for event in self._run_agent_with_validation(
          agent.analyze_blindspots_agent, ctx
      ):
        yield event
    except Exception as e:
      logger.error('Error in analyze_blindspots: %s', e, exc_info=True)
      # Continue workflow even if this fails
    
    logger.info('=== Phase 4: Analysis and Synthesis COMPLETE ===')

  async def _run_research_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 5: Search inquiry strategist and targeted research."""
    logger.info('=== Phase 5: Targeted Research ===')
    workflow_state.phase = 'research'
    
    # Search Inquiry Strategist
    async for event in self._run_agent_with_validation(
        agent.search_inquiry_strategist_agent, ctx
    ):
      yield event

    # Conduct Research (dual-track)
    async for event in self._run_agent_with_validation(
        agent.conduct_research_agent, ctx
    ):
      yield event
    
    # Validate additional CER facts were registered
    cer_registry = ctx.session.state.get('cer_registry', [])
    logger.info('After conduct_research: CER registry contains %d facts', len(cer_registry))

  async def _run_adjudication_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 6: Evidence adjudication, null adjudication, and case file creation."""
    logger.info('=== Phase 6: Adjudication and Case File ===')
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
    
    # Validate parallel agent outputs
    for sub_agent in [agent.evidence_adjudicator_agent, agent.null_adjudicator_agent]:
      output_key = getattr(sub_agent, 'output_key', None)
      if output_key:
        output = ctx.session.state.get(output_key)
        if output:
          if isinstance(output, dict):
            output_text = json.dumps(output)
          elif isinstance(output, str):
            output_text = output
          else:
            output_text = str(output)
          validation_result = validate_agent_output_by_key(
              output_text, output_key, sub_agent.name
          )
          if not validation_result.valid:
            logger.warning('Validation failed for parallel agent %s: %s',
                          sub_agent.name, validation_result.error)
        else:
          logger.debug('No output found in state for parallel agent %s (key: %s)',
                      sub_agent.name, output_key)

    # Case File
    async for event in self._run_agent_with_validation(
        agent.case_file_agent, ctx
    ):
      yield event

  async def _run_coverage_validation_phase(
      self,
      ctx: InvocationContext,
      workflow_state: ThinkRemixWorkflowState,
  ) -> AsyncGenerator[Event, None]:
    """Phase 7: Coverage validation loop (regenerate case file if needed)."""
    logger.info('=== Phase 7: Coverage Validation ===')
    workflow_state.phase = 'coverage_validation'
    max_attempts = self._config.max_coverage_validator_attempts

    while workflow_state.coverage_validator_attempts < max_attempts:
      workflow_state.coverage_validator_attempts += 1
      
      # Run Coverage Validator
      async for event in self._run_agent_with_validation(
          agent.coverage_validator_agent, ctx
      ):
        yield event

      # Check validation result
      validation_result = ctx.session.state.get('coverage_validation')
      if validation_result and isinstance(validation_result, dict):
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
          async for event in self._run_agent_with_validation(
              agent.case_file_agent, ctx
          ):
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
    logger.info('=== Phase 8: Final Synthesis ===')
    workflow_state.phase = 'final'
    
    # Robustness Calculator
    async for event in self._run_agent_with_validation(
        agent.robustness_calculator_agent, ctx
    ):
      yield event

    # QA Agent
    async for event in self._run_agent_with_validation(
        agent.qa_agent, ctx
    ):
      yield event

    # Final Arbiter
    async for event in self._run_agent_with_validation(
        agent.final_arbiter_agent, ctx
    ):
      yield event

  @override
  async def _run_live_impl(
      self, ctx: InvocationContext
  ) -> AsyncGenerator[Event, None]:
    """Live mode not supported for custom workflow."""
    raise NotImplementedError('Live mode not supported for ThinkRemixWorkflowAgent.')
