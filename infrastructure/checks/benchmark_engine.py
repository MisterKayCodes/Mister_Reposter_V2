import asyncio, time, random, statistics, os, shutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any

# --- 🧪 THE GAUNTLET: BENCHMARK ENGINE (PHASE 2) ---
# Purpose: High-fidelity stress testing for Async Loops and Database Contention.

@dataclass
class Metric:
    pair_id: int
    started_at: float
    ended_at: float = 0.0
    status: str = "pending"
    error: str = None

    @property
    def latency(self):
        return (self.ended_at - self.started_at) * 1000 if self.ended_at else 0

class VirtualTelegram:
    """Mock Telethon client that simulates high-speed message delivery."""
    def __init__(self, failure_rate=0.0):
        self.failure_rate = failure_rate
        self.sent_count = 0
        self.total_bytes = 0

    async def send_message(self, dest, text):
        self.sent_count += 1
        # Simulate network flight time (10ms - 50ms)
        await asyncio.sleep(random.uniform(0.01, 0.05))
        
        if random.random() < self.failure_rate:
            raise Exception("Simulated Network Timeout")
        return {"id": random.randint(1000, 9999)}

class BenchmarkEngine:
    def __init__(self, concurrent_pairs=100, failure_rate=0.0):
        self.concurrent_pairs = concurrent_pairs
        self.failure_rate = failure_rate
        self.metrics: List[Metric] = []
        self.vt = VirtualTelegram(failure_rate)
        self.is_running = False

    async def _simulate_handler(self, pair_id: int, message_text: str):
        """Simulates the RepostEngine's processing loop."""
        metric = Metric(pair_id=pair_id, started_at=time.perf_counter())
        self.metrics.append(metric)
        
        try:
            # 1. Simulate DB Lookup (1ms - 5ms)
            await asyncio.sleep(random.uniform(0.001, 0.005))
            
            # 2. Simulate Logic/Filtering (1ms)
            await asyncio.sleep(0.001)
            
            # 3. Virtual Send
            await self.vt.send_message("dest_channel", message_text)
            
            metric.status = "success"
        except Exception as e:
            metric.status = "failed"
            metric.error = str(e)
        finally:
            metric.ended_at = time.perf_counter()

    async def run_burst_scenario(self):
        """SCENARIO A: The Burst - Everything happens at once."""
        print(f"\n[Scenario A] THE BURST: Firing {self.concurrent_pairs} concurrent updates...")
        start_time = time.perf_counter()
        
        tasks = []
        for i in range(self.concurrent_pairs):
            tasks.append(self._simulate_handler(i, f"Shock message {i}"))
        
        await asyncio.gather(*tasks)
        dur = time.perf_counter() - start_time
        return dur

    async def run_sustained_scenario(self, duration=10, mps=10):
        """SCENARIO B: The Marathon - Constant high load."""
        print(f"\n[Scenario B] THE MARATHON: {mps} msgs/sec for {duration} seconds...")
        start_time = time.perf_counter()
        end_run = start_time + duration
        
        msg_id = 0
        while time.perf_counter() < end_run:
            batch = []
            for _ in range(mps):
                batch.append(self._simulate_handler(msg_id % self.concurrent_pairs, f"Steady message {msg_id}"))
                msg_id += 1
            await asyncio.gather(*batch)
            await asyncio.sleep(1.0) # Sustain MPS rate
        
        dur = time.perf_counter() - start_time
        return dur

    def report_results(self, total_duration):
        successes = [m for m in self.metrics if m.status == "success"]
        failures = [m for m in self.metrics if m.status == "failed"]
        latencies = [m.latency for m in successes]
        
        print("\n" + "="*50)
        print("GAUNTLET BENCHMARK COMPLETE")
        print("="*50)
        print(f"Total Requests: {len(self.metrics)}")
        print(f"Throughput:     {len(self.metrics)/total_duration:.2f} req/sec")
        print(f"Success Rate:   {(len(successes)/len(self.metrics))*100:.1f}%")
        
        if latencies:
            print(f"\n--- LATENCY ---")
            print(f"Average:        {statistics.mean(latencies):.2f} ms")
            print(f"P50 (Median):   {statistics.median(latencies):.2f} ms")
            print(f"P95 (Slowest):  {statistics.quantiles(latencies, n=20)[18]:.2f} ms")
            print(f"P99 (Extreme):  {max(latencies):.2f} ms")
        
        if failures:
            print(f"\n--- FAILURES ---")
            print(f"Total Errors:   {len(failures)}")
            print(f"Primary Cause:  {failures[0].error}")
            
        print("="*50)

async def main():
    # Configure Gauntlet
    engine = BenchmarkEngine(concurrent_pairs=100, failure_rate=0.05)
    
    total_start = time.perf_counter()
    
    # 1. Run Scenarios
    await engine.run_burst_scenario()
    await engine.run_sustained_scenario(duration=5, mps=20)
    
    total_duration = time.perf_counter() - total_start
    
    # 2. Report
    engine.report_results(total_duration)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
