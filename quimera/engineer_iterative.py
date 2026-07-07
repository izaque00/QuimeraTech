"""
Iterative Engineer Loop — keeps fixing until build is completely clean.

Key improvement over v4: the loop doesn't stop after one fix.
It rebuilds, re-checks, and fixes again until zero errors remain
(or max iterations exceeded).
"""
import asyncio
import logging
from typing import List, Optional

logger = logging.getLogger("quimera.engineer_iterative")


class IterativeEngineer:
    """
    Fix→Rebuild→Check→Repeat until clean.

    Unlike the single-pass Engineer Loop, this continues applying
    fixes until the build passes completely or max_iterations is hit.
    """

    def __init__(self, engineer):
        self.engineer = engineer
        self.fix_history = []  # Track what we fixed and whether it worked

    async def fix_until_clean(self, max_rounds: int = 10, 
                              max_per_round: int = 3) -> dict:
        """
        Keep fixing until:
        1. Build passes (return code 0)
        2. Max rounds exceeded
        3. No more hypotheses generated

        Returns: {
            'rounds': int,
            'total_fixes': int,
            'final_build_ok': bool,
            'remaining_errors': List[str],
            'history': List[dict],
        }
        """
        import subprocess

        stats = {
            'rounds': 0,
            'total_fixes': 0,
            'final_build_ok': False,
            'remaining_errors': [],
            'history': [],
        }

        for round_num in range(1, max_rounds + 1):
            stats['rounds'] = round_num
            logger.info(f"🔄 ITERATIVE ROUND {round_num}/{max_rounds}")

            # Check current build status
            errors = self.engineer._try_build(
                self.engineer.project_root, 
                self.engineer.build_system
            )

            if not errors:
                logger.info("✅ BUILD CLEAN — done!")
                stats['final_build_ok'] = True
                break

            stats['remaining_errors'] = errors[:5]
            logger.info(f"  ❌ {len(errors)} errors remain")

            # Run one fix cycle
            ctx = await self.engineer.solve(
                objective=f"Fix remaining build errors (round {round_num})",
                max_iterations=max_per_round,
            )

            round_history = {
                'round': round_num,
                'errors_before': len(errors),
                'hypotheses': len(ctx.hypotheses),
                'successful': len(ctx.successful_hypotheses),
                'failed': len(ctx.failed_hypotheses),
            }
            stats['history'].append(round_history)
            stats['total_fixes'] += len(ctx.successful_hypotheses)

            if not ctx.hypotheses:
                logger.warning("  No hypotheses generated — giving up")
                break

            if not ctx.successful_hypotheses and not ctx.failed_hypotheses:
                logger.warning("  No fixes attempted — giving up")
                break

        # Final check
        final_errors = self.engineer._try_build(
            self.engineer.project_root,
            self.engineer.build_system
        )
        if not final_errors:
            stats['final_build_ok'] = True
        stats['remaining_errors'] = final_errors[:10]

        return stats


async def iterative_fix(project_root: str, build_system: str = "make",
                        max_rounds: int = 10) -> dict:
    """
    Convenience: fix a broken project until it compiles.
    
    Usage:
        result = await iterative_fix("./my_broken_project")
        print(f"Fixed in {result['rounds']} rounds: {result['final_build_ok']}")
    """
    from quimera.engineer import QuimeraEngineer

    eng = QuimeraEngineer(
        project_root=project_root,
        build_system=build_system,
    )
    iterative = IterativeEngineer(eng)
    return await iterative.fix_until_clean(max_rounds=max_rounds)
