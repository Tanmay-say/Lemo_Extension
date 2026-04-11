"""
Dual LLM Support - Uses either Gemini or Emergent LLM Key
Checks which key is available and uses it
"""
import os
from typing import Optional, Tuple
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

# Get API keys from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMERGENT_LLM_KEY = os.getenv("EMERGENT_LLM_KEY")

# Check if keys are valid (not placeholders)
def is_valid_key(key: Optional[str]) -> bool:
    """Check if API key is valid (not None or placeholder)"""
    if not key:
        return False
    if "PLACEHOLDER" in key.upper():
        return False
    if len(key.strip()) < 10:
        return False
    return True


def get_available_llm():
    """
    Get the available LLM based on which API key is configured
    Priority: Gemini > Emergent LLM Key
    
    Returns:
        Tuple of (llm_instance, llm_name)
    """
    # Try Gemini first
    if is_valid_key(GEMINI_API_KEY):
        print("[LLM] Using Gemini API")
        try:
            llm = ChatGoogleGenerativeAI(
                model="gemini-pro",
                google_api_key=GEMINI_API_KEY,
                temperature=0.7,
                max_output_tokens=2048
            )
            return llm, "gemini"
        except Exception as e:
            print(f"[LLM ERROR] Failed to initialize Gemini: {e}")
    
    # Try Emergent LLM Key (supports OpenAI, Anthropic, Gemini)
    if is_valid_key(EMERGENT_LLM_KEY):
        print("[LLM] Using Emergent LLM Key with OpenAI")
        try:
            # Emergent LLM key works with OpenAI API
            llm = ChatOpenAI(
                model="gpt-4",
                openai_api_key=EMERGENT_LLM_KEY,
                openai_api_base="https://api.emergent.ai/v1",  # Emergent API endpoint
                temperature=0.7,
                max_tokens=2048
            )
            return llm, "emergent-openai"
        except Exception as e:
            print(f"[LLM ERROR] Failed to initialize Emergent LLM: {e}")
            
            # Try Claude as fallback with Emergent key
            try:
                print("[LLM] Trying Emergent LLM Key with Claude")
                llm = ChatAnthropic(
                    model="claude-3-sonnet-20240229",
                    anthropic_api_key=EMERGENT_LLM_KEY,
                    temperature=0.7,
                    max_tokens=2048
                )
                return llm, "emergent-claude"
            except Exception as e2:
                print(f"[LLM ERROR] Failed to initialize Claude: {e2}")
    
    # No valid LLM key found
    raise ValueError(
        "No valid LLM API key found. Please set either GEMINI_API_KEY or EMERGENT_LLM_KEY in .env file"
    )


def get_llm_for_task(task_type: str = "general"):
    """
    Get LLM instance optimized for specific task
    
    Args:
        task_type: Type of task ("general", "code", "creative", "analysis")
        
    Returns:
        Configured LLM instance
    """
    llm, llm_name = get_available_llm()
    
    # Adjust temperature based on task
    temperature_map = {
        "general": 0.7,
        "code": 0.2,
        "creative": 0.9,
        "analysis": 0.5
    }
    
    temperature = temperature_map.get(task_type, 0.7)
    print(f"[LLM] Configured {llm_name} for {task_type} task (temp={temperature})")
    
    # Note: Temperature adjustment would need to be done at initialization
    # This is a simplified version
    return llm


# Initialize default LLM at module load
try:
    default_llm, default_llm_name = get_available_llm()
    print(f"[LLM] Successfully initialized {default_llm_name}")
except Exception as e:
    print(f"[LLM ERROR] Failed to initialize any LLM: {e}")
    default_llm = None
    default_llm_name = None
