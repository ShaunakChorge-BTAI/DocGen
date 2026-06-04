"""
Ollama Integration Service for SQL Optimization
Calls local Ollama instance to generate optimization suggestions
"""

import asyncio
import json
import logging
import re
from typing import Optional, Dict, Any
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class OllamaOptimizer:
    """Local Ollama client for SQL optimization suggestions"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 11434,
        model: str = "mistral",
        timeout_seconds: int = 30
    ):
        self.host = host
        self.port = port
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.base_url = f"http://{host}:{port}"
        self.client = httpx.AsyncClient(timeout=timeout_seconds)

    async def check_availability(self) -> Dict[str, Any]:
        """Check if Ollama is running and model is available"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            models = response.json().get("models", [])
            model_names = [m.get("name", "").split(":")[0] for m in models]

            return {
                "available": True,
                "models": model_names,
                "model_loaded": any(self.model in name for name in model_names),
                "error": None,
            }
        except Exception as e:
            logger.error(f"Ollama availability check failed: {e}")
            return {
                "available": False,
                "models": [],
                "model_loaded": False,
                "error": str(e),
            }

    async def optimize_sql(
        self,
        sql_code: str,
        object_type: str,
        rule_id: str,
        issue_description: str,
        rule_recommendation: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Call Ollama to suggest SQL optimization

        Args:
            sql_code: Original SQL code
            object_type: Type (Function, Procedure, View, etc.)
            rule_id: Rule that triggered the finding (e.g., PERF001)
            issue_description: What's wrong with the query
            rule_recommendation: Optional guidance from the rule

        Returns:
            {
                "success": bool,
                "suggested_sql": "optimized SQL code" or None if failed,
                "explanation": "why this is better",
                "confidence_score": 0.85,
                "estimated_improvement_pct": 35,
                "estimated_risk_level": "low",
                "response_time_ms": 8500,
                "model": "mistral",
                "error": None or error message
            }
        """
        start_time = datetime.now()

        try:
            # Build the prompt
            prompt = self._build_optimization_prompt(
                sql_code, object_type, rule_id, issue_description, rule_recommendation
            )

            # Call Ollama
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.3,  # Lower temp = more deterministic
                },
            )

            response.raise_for_status()
            result = response.json()

            # Parse the response
            generated_text = result.get("response", "")
            response_time_ms = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )

            # Extract structured data from response
            parsed = self._parse_ollama_response(generated_text)

            return {
                "success": True,
                "suggested_sql": parsed.get("suggested_sql"),
                "explanation": parsed.get("explanation"),
                "confidence_score": parsed.get("confidence_score", 0.7),
                "estimated_improvement_pct": parsed.get("estimated_improvement_pct", 20),
                "estimated_risk_level": parsed.get("estimated_risk_level", "medium"),
                "response_time_ms": response_time_ms,
                "model": self.model,
                "error": None,
                "full_response": generated_text,  # For debugging
            }

        except asyncio.TimeoutError:
            logger.error(f"Ollama request timed out after {self.timeout_seconds}s")
            return {
                "success": False,
                "suggested_sql": None,
                "explanation": "Ollama request timed out. Please try again.",
                "confidence_score": 0,
                "estimated_improvement_pct": 0,
                "estimated_risk_level": "unknown",
                "response_time_ms": self.timeout_seconds * 1000,
                "model": self.model,
                "error": "Timeout",
            }

        except httpx.HTTPError as e:
            logger.error(f"Ollama HTTP error: {e}")
            return {
                "success": False,
                "suggested_sql": None,
                "explanation": "Failed to connect to Ollama. Is it running?",
                "confidence_score": 0,
                "estimated_improvement_pct": 0,
                "estimated_risk_level": "unknown",
                "response_time_ms": int(
                    (datetime.now() - start_time).total_seconds() * 1000
                ),
                "model": self.model,
                "error": f"HTTP Error: {str(e)}",
            }

        except Exception as e:
            logger.error(f"Unexpected error in optimize_sql: {e}")
            return {
                "success": False,
                "suggested_sql": None,
                "explanation": f"Error: {str(e)}",
                "confidence_score": 0,
                "estimated_improvement_pct": 0,
                "estimated_risk_level": "unknown",
                "response_time_ms": int(
                    (datetime.now() - start_time).total_seconds() * 1000
                ),
                "model": self.model,
                "error": str(e),
            }

    def _build_optimization_prompt(
        self,
        sql_code: str,
        object_type: str,
        rule_id: str,
        issue_description: str,
        rule_recommendation: Optional[str] = None,
    ) -> str:
        """Build the optimization prompt for Ollama"""

        prompt = f"""You are a SQL optimization expert. Optimize this {object_type}.

Rule Triggered: {rule_id}
Issue: {issue_description}

Original SQL:
```sql
{sql_code}
```

{f'Hint: {rule_recommendation}' if rule_recommendation else ''}

Provide your response in this exact format (JSON):
{{
  "suggested_sql": "Your optimized SQL code here",
  "explanation": "Brief explanation of changes and why they improve performance",
  "confidence_score": 0.85,
  "estimated_improvement_pct": 30,
  "estimated_risk_level": "low"
}}

Focus on:
1. Index usage (can queries use indexes better?)
2. JOIN efficiency (nested loops vs hash joins)
3. Column selection (SELECT * vs specific columns)
4. Subquery optimization (flattening, materialization)
5. Data type conversions (implicit conversions blocking index use)

Risk levels: low (safe), medium (needs testing), high (risky, needs approval)
Improvement %: realistic estimate (5-95%), not optimistic
Confidence: 0.0-1.0, based on certainty of suggestion
"""
        return prompt

    def _parse_ollama_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Ollama's response to extract structured data"""

        try:
            # Try to find JSON in the response
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                return {
                    "suggested_sql": data.get("suggested_sql", ""),
                    "explanation": data.get("explanation", ""),
                    "confidence_score": float(data.get("confidence_score", 0.7)),
                    "estimated_improvement_pct": int(
                        data.get("estimated_improvement_pct", 20)
                    ),
                    "estimated_risk_level": data.get("estimated_risk_level", "medium"),
                }
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse Ollama JSON response: {e}")

        # Fallback: return the full response as explanation
        return {
            "suggested_sql": "",
            "explanation": response_text[:500],  # First 500 chars
            "confidence_score": 0.5,
            "estimated_improvement_pct": 20,
            "estimated_risk_level": "medium",
        }

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


# Singleton instance
_optimizer: Optional[OllamaOptimizer] = None


async def get_optimizer(
    host: str = "localhost",
    port: int = 11434,
    model: str = "mistral",
) -> OllamaOptimizer:
    """Get or create the Ollama optimizer instance"""
    global _optimizer
    if _optimizer is None:
        _optimizer = OllamaOptimizer(host=host, port=port, model=model)
    return _optimizer


async def check_ollama_health() -> Dict[str, Any]:
    """Check if Ollama is available"""
    optimizer = await get_optimizer()
    return await optimizer.check_availability()
