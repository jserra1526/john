"""Command line: python -m milkopt INPUT.xlsx [-o RESULTS.xlsx]"""

import argparse
import sys
import time

from .data import InputError, load_workbook
from .model import MilkModel
from .report import print_summary, write_excel


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Optimise milk allocation and product mix over a season.")
    ap.add_argument("input", help="Input Excel workbook")
    ap.add_argument("-o", "--output", default="results.xlsx", help="Results Excel workbook")
    ap.add_argument("-v", "--verbose", action="store_true", help="Show solver log")
    args = ap.parse_args(argv)

    try:
        data = load_workbook(args.input)
    except InputError as e:
        print(e, file=sys.stderr)
        return 2
    t0 = time.time()
    model = MilkModel(data)
    print(f"Model: {len(model.prob.variables()):,} variables, {len(model.prob.constraints):,} constraints")
    res = model.solve(msg=args.verbose)
    print(f"Solved in {time.time() - t0:.1f}s")
    print_summary(res)
    if res.status != "Optimal":
        return 1
    write_excel(res, args.output)
    print(f"\nResults written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
