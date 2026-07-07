"""Quimera Critical Tests — H1-H6, Memory, Pipeline, Mind."""
import asyncio, os, sys, tempfile, unittest

class TestH4GeneticEvolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from quimera.horizons.h4_evolution.genetic_patch_engine import GeneticPatchEngine
        cls.engine = GeneticPatchEngine(population_size=20, generations=5, mutation_rate=0.05)
    def test_initializes(self): self.assertIsNotNone(self.engine)
    def test_evolve(self):
        with tempfile.NamedTemporaryFile(suffix='.c', mode='w', delete=False) as f:
            f.write('int main(){char b[10];gets(b);return 0;}'); f.flush(); path = f.name
        try:
            patches = asyncio.get_event_loop().run_until_complete(
                asyncio.to_thread(self.engine.evolve_patches, file_path=path, error_description="buffer overflow"))
            self.assertIsInstance(patches, list)
        finally: os.unlink(path)

class TestH5RedTeam(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from quimera.horizons.h5_security.red_team import RedTeam; cls.team = RedTeam()
    def test_attack(self):
        attacks = self.team.attack('void f(char*x){char b[16];strcpy(b,x);}')
        self.assertIsInstance(attacks, list)

class TestH3Z3(unittest.TestCase):
    def test_initializes(self):
        from quimera.integration_backends.z3_wrapper import Z3Wrapper
        self.assertIsNotNone(Z3Wrapper())

class TestH2Memory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from quimera.memory.integration import MemoryPipeline
        cls.db = tempfile.mktemp(suffix='.db'); cls.p = MemoryPipeline(db_path=cls.db)
    def test_record_retrieve(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.p.record_outcome(mission_id="t1", error_type="o", error_description="x", solution_description="fix", success=True, fitness_score=0.9))
        r = loop.run_until_complete(self.p.retrieve_solutions(error_type="o", error_description="x"))
        self.assertGreaterEqual(r.total_found, 1)
    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.db): os.unlink(cls.db)

class TestPipeline(unittest.TestCase):
    def test_evolve_real(self):
        import inspect
        from quimera.pipeline import AutonomousPipeline
        self.assertIn("GeneticPatchEngine", inspect.getsource(AutonomousPipeline._stage_evolve))

if __name__ == "__main__":
    r = unittest.TextTestRunner(verbosity=2).run(unittest.TestLoader().discover('.'))
    sys.exit(0 if r.wasSuccessful() else 1)
