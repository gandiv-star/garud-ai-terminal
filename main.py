from sector.sector_analysis import SectorAnalysisEngine

print("--- Verify: SectorAnalysisEngine.rank_sectors() ---")
try:
    engine = SectorAnalysisEngine()
    rankings = engine.rank_sectors()
    for r in rankings:
        print(f"{r.sector}: sector={r.sector_return}% index={r.index_return}% rel_strength={r.relative_strength:.2f}")
except Exception as e:
    print(f"FAILED: {e}")
