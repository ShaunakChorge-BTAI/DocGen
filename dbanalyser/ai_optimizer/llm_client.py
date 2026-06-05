import os
import logging
import requests
from typing import NamedTuple, Optional

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_URL", "http://172.19.26.252:11434")
LLM_MODEL       = os.environ.get("LLM_MODEL",  "llama3.1")

class LLMResult(NamedTuple):
    text: Optional[str]
    error: Optional[str]
    latency_ms: int

def call_llm(prompt: str, timeout: int = 60) -> LLMResult:
    """Call Ollama LLM with defensive logging and structured results."""
    endpoint = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": False
    }
    
    logger.info(f"Calling Ollama at {endpoint} with model {LLM_MODEL} (prompt length: {len(prompt)} chars)")
    
    try:
        response = requests.post(endpoint, json=payload, timeout=timeout)
        latency_ms = int(response.elapsed.total_seconds() * 1000)
        
        if response.status_code == 200:
            result = response.json().get("response", "")
            logger.info(f"Ollama call successful, latency: {latency_ms}ms")
            return LLMResult(text=result, error=None, latency_ms=latency_ms)
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(f"Ollama call failed: {error_msg}")
            return LLMResult(text=None, error=error_msg, latency_ms=latency_ms)
            
    except requests.exceptions.Timeout:
        error_msg = f"Request timed out after {timeout} seconds"
        logger.error(f"Ollama call timeout: {error_msg}")
        return LLMResult(text=None, error=error_msg, latency_ms=timeout * 1000)
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Connection error: {str(e)}"
        logger.error(f"Ollama connection error: {error_msg}")
        return LLMResult(text=None, error=error_msg, latency_ms=0)
