"""Command line entry point:  python -m milk_opt [data_dir] [--out output_dir]"""

import argparse

from .data import load_data
from .model import DEFAULT_DUMP_PENALTY_PER_T, optimise
from .report import summary, write_outputs


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Optimise milk allocation and product mix.")
    parser.add_argument("data_dir", nargs="?", default="data/sample", help="directory of input CSVs")
    parser.add_argument("--out", default="output", help="directory for result CSVs")
    parser.add_argument("--allow-uncollected", action="store_true",
                        help="milk supply is an upper bound rather than must-take")
    parser.add_argument("--dump-penalty", type=float, default=DEFAULT_DUMP_PENALTY_PER_T,
                        help="cost per tonne of milk that cannot be processed or sold")
    parser.add_argument("--time-limit", type=float, default=None, help="solver time limit (s)")
    parser.add_argument("--verbose", action="store_true", help="show solver log")
    args = parser.parse_args(argv)

    data = load_data(args.data_dir)
    sol = optimise(data, must_take_milk=not args.allow_uncollected,
                   dump_penalty_per_t=args.dump_penalty, msg=args.verbose, time_limit=args.time_limit)
    print(summary(sol))
    print(f"\nResults written to {write_outputs(sol, args.out)}/")


if __name__ == "__main__":
    main()
