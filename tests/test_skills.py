from agent_core.skills.builtin import UnitNormalizerSkill

skill = UnitNormalizerSkill()

# Test _normalize directly
assert skill._normalize("$1.2 billion") == 1_200_000_000.0
assert skill._normalize("1,200,000")    == 1_200_000.0
assert skill._normalize("3.5%")         == 0.035
assert skill._normalize("45.6 million") == 45_600_000.0
assert skill._normalize("1.2B")         == 1_200_000_000.0
assert skill._normalize("500M")         == 500_000_000.0

print("All tests passed!")