from typing import Dict, Any
from agent.nodes import AgentState, load_profile_node, determine_intent_node, scout_node, planner_node, rag_node

try:
    from langgraph.graph import StateGraph, END
    _HAS_LANGGRAPH = True
except ImportError:
    _HAS_LANGGRAPH = False

def build_pathfinder_graph():
    """Build and compile LangGraph orchestration graph."""
    if not _HAS_LANGGRAPH:
        return None
        
    try:
        workflow = StateGraph(AgentState)
        
        # Add Nodes
        workflow.add_node("load_profile", load_profile_node)
        workflow.add_node("determine_intent", determine_intent_node)
        workflow.add_node("scout", scout_node)
        workflow.add_node("planner", planner_node)
        workflow.add_node("rag", rag_node)
        
        # Set Entry Point
        workflow.set_entry_point("load_profile")
        
        # Add Edges
        workflow.add_edge("load_profile", "determine_intent")
        
        # Conditional Routing
        def route_by_intent(state: AgentState) -> str:
            intent = state.get("intent", "question")
            if intent == "opportunity":
                return "scout"
            elif intent == "learning":
                return "planner"
            else:
                return "rag"
                
        workflow.add_conditional_edges(
            "determine_intent",
            route_by_intent,
            {
                "scout": "scout",
                "planner": "planner",
                "rag": "rag"
            }
        )
        
        # Add Terminal Edges
        workflow.add_edge("scout", END)
        workflow.add_edge("planner", END)
        workflow.add_edge("rag", END)
        
        return workflow.compile()
    except Exception as e:
        print(f"LangGraph compilation error: {e}. Using fallback runner.")
        return None

# Global compiled graph instance
compiled_graph = build_pathfinder_graph()

def run_agent_workflow(user_input: str) -> Dict[str, Any]:
    """Execute the Pathfinder AI agent workflow (LangGraph or fallback execution)."""
    initial_state: AgentState = {
        "user_input": user_input,
        "profile_loaded": False,
        "intent": "unknown",
        "response": "",
        "metadata": {}
    }
    
    if compiled_graph is not None:
        try:
            final_state = compiled_graph.invoke(initial_state)
            return {
                "status": "success",
                "intent": final_state.get("intent"),
                "response": final_state.get("response"),
                "metadata": final_state.get("metadata", {})
            }
        except Exception as e:
            print(f"LangGraph invocation error: {e}. Executing sequential fallback.")
            
    # Sequential Fallback Execution
    state = load_profile_node(initial_state)
    state = determine_intent_node(state)
    
    intent = state.get("intent")
    if intent == "opportunity":
        state = scout_node(state)
    elif intent == "learning":
        state = planner_node(state)
    else:
        state = rag_node(state)
        
    return {
        "status": "success",
        "intent": state.get("intent"),
        "response": state.get("response"),
        "metadata": state.get("metadata", {})
    }
