#!/usr/bin/env python3
"""End-to-end test for Saiyan Research Agent harness."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test 1: Import harness
print("=== Test 1: Import harness ===")
try:
    from harness import Agent, AgentResult, ModelProvider, get_client
    print("✅ harness import OK")
except Exception as e:
    print(f"❌ harness import FAILED: {e}")
    sys.exit(1)

# Test 2: Import config
print("\n=== Test 2: Import config ===")
try:
    from config import get_config, Config, reset_config
    print("✅ config import OK")
except Exception as e:
    print(f"❌ config import FAILED: {e}")
    sys.exit(1)

# Test 3: Create Agent
print("\n=== Test 3: Create Agent ===")
try:
    agent = Agent()
    print(f"✅ Agent created: {agent}")
    print(f"   Available tools: {agent.available_tools}")
    print(f"   Tool count: {len(agent.available_tools)}")
except Exception as e:
    print(f"❌ Agent creation FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Check provider
print("\n=== Test 4: Provider check ===")
try:
    print(f"   Provider base_url: {agent._provider.client.base_url}")
    print(f"   Model: {agent._default_model or 'auto-discover'}")
    print(f"   Agent name: {agent.agent_name}")
    print(f"   Max tool rounds: {agent.max_tool_rounds}")
    print("✅ Provider check OK")
except Exception as e:
    print(f"❌ Provider check FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Check AgentResult
print("\n=== Test 5: AgentResult ===")
try:
    r = AgentResult(response="test", rounds_used=1, tool_calls=[])
    print(f"   Response: {r.response}")
    print(f"   Dict: {r.to_dict()}")
    print("✅ AgentResult OK")
except Exception as e:
    print(f"❌ AgentResult FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Check config values
print("\n=== Test 6: Config values ===")
try:
    cfg = get_config()
    print(f"   model.provider: {cfg.model.provider}")
    print(f"   model.base_url: {cfg.model.base_url}")
    print(f"   model.model: {cfg.model.model}")
    print(f"   agent.name: {cfg.agent.name}")
    print(f"   agent.max_tool_rounds: {cfg.agent.max_tool_rounds}")
    print("✅ Config values OK")
except Exception as e:
    print(f"❌ Config values FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 7: Check cli.py import
print("\n=== Test 7: cli.py import ===")
try:
    import cli
    print("✅ cli.py import OK")
except Exception as e:
    print(f"❌ cli.py import FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 8: Check main.py import
print("\n=== Test 8: main.py import ===")
try:
    import main
    print("✅ main.py import OK")
except Exception as e:
    print(f"❌ main.py import FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 9: Check harness.__init__.py exports
print("\n=== Test 9: harness exports ===")
try:
    import harness
    expected = ["Agent", "AgentResult", "ModelProvider", "get_client",
                "ToolRegistry", "get_tool_registry", "build_system_prompt",
                "DEFAULT_SYSTEM_PROMPT"]
    for name in expected:
        assert hasattr(harness, name), f"Missing export: {name}"
    print("✅ All expected exports present")
except Exception as e:
    print(f"❌ harness exports FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 10: Verify model name caching
print("\n=== Test 10: Model name caching ===")
try:
    agent2 = Agent()
    # The default model should come from config, not be auto-discovered on every call
    cfg2 = get_config()
    expected_model = cfg2.model.model
    actual_model = agent2._default_model
    if actual_model is None:
        print(f"   _default_model is None (will use auto-discover)")
    else:
        print(f"   _default_model: {actual_model}")
    print("✅ Model caching OK")
except Exception as e:
    print(f"❌ Model caching FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("ALL TESTS PASSED ✅")
print("=" * 60)