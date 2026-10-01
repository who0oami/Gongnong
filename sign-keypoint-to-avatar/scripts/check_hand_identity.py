"""Regression checks for anatomical assignment under crossed arms and occlusion."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'extractor'))
from refine_hands import wrist_association

# Anatomical left on either side of the image is still left.
assert wrist_association((20,30), (20,30), (80,30), 50)
assert wrist_association((80,30), (80,30), (20,30), 50)
# Candidate belonging to the other arm must never be relabelled by x position.
assert not wrist_association((80,30), (20,30), (80,30), 50)
# Coincident/crossing wrists are ambiguous, not silently swapped.
assert not wrist_association((50,30), (49,30), (51,30), 50)
# Distant false positives and close-distance ambiguity are rejected.
assert not wrist_association((200,30), (20,30), (80,30), 50)
assert not wrist_association((0,0), (0,0), (1,0), 50)
print('6 anatomical identity regression checks passed')
