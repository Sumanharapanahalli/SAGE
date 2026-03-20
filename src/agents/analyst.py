import json
import logging
from typing import Dict, Any, Tuple
from src.core.llm_gateway import llm_gateway
from src.core.project_loader import project_config
from src.memory.vector_store import vector_memory
from src.memory.audit_logger import audit_logger

class AnalystAgent:
    def __init__(self):
        self.logger = logging.getLogger("AnalystAgent")

    def analyze_log(self, log_entry: str) -> Dict[str, Any]:
        """
        Main Analysis Loop:
        1. Search Memory (Have we seen this?)
        2. Ask LLM (Reasoning) — prompts loaded from active project config
        3. Audit (Compliance)
        4. Return Proposal
        """
        self.logger.info(f"Analyzing log: {log_entry[:50]}...")

        # 1. RAG Lookup
        context_docs = vector_memory.search(log_entry, k=2)
        context_str = "\n".join(context_docs) if context_docs else "No prior context found."

        # 2. Construct Prompt — domain-specific via project_loader
        system_prompt, user_tmpl = project_config.get_analyst_prompts()
        # Inject solution_context.md standing instructions (if present)
        sol_ctx = project_config.solution_context
        if sol_ctx:
            system_prompt = sol_ctx + "\n\n" + system_prompt
        # Inject SKILL.md domain knowledge when available
        skill = project_config.skill_content
        if skill:
            system_prompt = system_prompt + "\n\n## Domain Skills\n" + skill
        user_prompt = user_tmpl.format(input=log_entry, context=context_str)

        # 3. LLM Inference
        try:
            response_text = llm_gateway.generate(user_prompt, system_prompt)
            # clean json markdown if present
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            analysis = json.loads(response_text)
        except json.JSONDecodeError:
            self.logger.error("LLM failed to produce valid JSON.")
            analysis = {
                "severity": "UNKNOWN",
                "root_cause_hypothesis": "AI Output Parsing Error",
                "recommended_action": "Manual Review Required",
                "raw_output": response_text
            }
        except Exception as e:
            self.logger.error(f"Analysis failed: {e}")
            return {"error": str(e)}

        # 4. Compliance Audit
        trace_id = audit_logger.log_event(
            actor="AnalystAgent",
            action_type="ANALYSIS_PROPOSAL",
            input_context=log_entry,
            output_content=json.dumps(analysis)
        )
        
        analysis["trace_id"] = trace_id
        return analysis

    def learn_from_feedback(self, log_entry: str, human_comment: str, original_analysis: Dict):
        """
        Ingest human corrections to improve future responses.
        """
        learning_text = (
            f"SCENARIO: Log Error '{log_entry}'\n"
            f"AI GUESS: {original_analysis.get('root_cause_hypothesis')}\n"
            f"HUMAN CORRECTION: {human_comment}\n"
            "LESSON: In future, prioritize the Human Correction."
        )
        
        # Save to Vector DB
        vector_memory.add_feedback(learning_text, metadata={"type": "human_feedback", "source": "AnalystAgent"})
        
        # Audit the feedback
        audit_logger.log_event(
            actor="Human_Engineer",
            action_type="FEEDBACK_LEARNING",
            input_context=json.dumps(original_analysis),
            output_content=human_comment
        )
        self.logger.info("Feedback digested and improved.")

analyst_agent = AnalystAgent()
