from enum import Enum


class Step(Enum):
    S1 = 0
    S6_SANITIZE = 1
    S2 = 2
    S3_GENERATE = 3
    S3_RESTORE = 4
    S4_GENERATE = 5
    S4_RESTORE = 6
    MARK_DRAFTED = 7

def step(session, card, note) -> Step | None:
    transitions = {
        'uploaded': Step.S1,
        'transcribed': Step.S6_SANITIZE,
        'sanitized': Step.S2,
        'analyzed': Step.S3_GENERATE, # Session 1 + card is absent
        'generated': Step.S3_RESTORE,
        ''

    }