import argparse

def format_time_left(minutes: int) -> str:
    if minutes <= 0: return "0m"
    if minutes < 60: return f"{minutes}m"
    hours = minutes // 60
    if hours < 24: return f"{hours}h {minutes % 60}m"
    days = hours // 24
    return f"{days}d {hours % 24}h"

def simulate(current, total, interval):
    remaining = max(0, total - current)
    time_left_min = remaining * interval
    time_str = format_time_left(time_left_min)
    
    print("-" * 30)
    print(f"SIMULATION RESULTS")
    print("-" * 30)
    print(f"Current Post:    {current}")
    print(f"Total Posts:      {total}")
    print(f"Remaining:       {remaining}")
    print(f"Schedule:        Every {interval} minutes")
    print(f"Estimated Time:  {time_str}")
    print("-" * 30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate post stats.")
    parser.add_argument("--current", type=int, default=50, help="Current message ID")
    parser.add_argument("--total", type=int, default=100, help="Total message count")
    parser.add_argument("--interval", type=int, default=30, help="Interval in minutes")
    
    args = parser.parse_args()
    simulate(args.current, args.total, args.interval)
