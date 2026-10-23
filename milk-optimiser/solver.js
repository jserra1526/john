// Two-phase dense simplex with Bland's rule.
// solveLP({ c: [..], rows: [{ a: [..], op: '<=' | '>=' | '=', b }] })
// minimises c·x subject to rows and x >= 0.
// Returns { status: 'optimal' | 'infeasible' | 'unbounded', x, value }.
function solveLP(lp) {
  const EPS = 1e-9;
  const n = lp.c.length;
  const rows = lp.rows.map(r => {
    if (r.b < 0) {
      const flip = { '<=': '>=', '>=': '<=', '=': '=' }[r.op];
      return { a: r.a.map(v => -v), op: flip, b: -r.b };
    }
    return { a: r.a.slice(), op: r.op, b: r.b };
  });
  const m = rows.length;
  let nSlack = 0, nArt = 0;
  rows.forEach(r => { if (r.op !== '=') nSlack++; if (r.op !== '<=') nArt++; });
  const cols = n + nSlack + nArt;
  const T = [], basis = [];
  let s = n, art = n + nSlack;
  const artCols = [];
  for (const r of rows) {
    const row = new Array(cols + 1).fill(0);
    for (let j = 0; j < n; j++) row[j] = r.a[j] || 0;
    row[cols] = r.b;
    if (r.op === '<=') { row[s] = 1; basis.push(s); s++; }
    else if (r.op === '>=') { row[s] = -1; s++; row[art] = 1; basis.push(art); artCols.push(art); art++; }
    else { row[art] = 1; basis.push(art); artCols.push(art); art++; }
    T.push(row);
  }

  function pivot(pr, pc) {
    const p = T[pr][pc];
    for (let j = 0; j <= cols; j++) T[pr][j] /= p;
    for (let i = 0; i < m; i++) {
      if (i === pr) continue;
      const f = T[i][pc];
      if (Math.abs(f) > EPS) for (let j = 0; j <= cols; j++) T[i][j] -= f * T[pr][j];
    }
    basis[pr] = pc;
  }

  // Run simplex minimising cost vector `cost` over allowed columns.
  function run(cost, allowed) {
    for (let iter = 0; iter < 5000; iter++) {
      // reduced costs
      let pc = -1;
      for (let j = 0; j < cols; j++) {
        if (!allowed[j] || basis.includes(j)) continue;
        let rc = cost[j];
        for (let i = 0; i < m; i++) rc -= cost[basis[i]] * T[i][j];
        if (rc < -EPS) { pc = j; break; } // Bland: first improving column
      }
      if (pc < 0) return 'optimal';
      let pr = -1, best = Infinity;
      for (let i = 0; i < m; i++) {
        if (T[i][pc] > EPS) {
          const ratio = T[i][cols] / T[i][pc];
          if (ratio < best - EPS || (Math.abs(ratio - best) <= EPS && basis[i] < basis[pr])) { best = ratio; pr = i; }
        }
      }
      if (pr < 0) return 'unbounded';
      pivot(pr, pc);
    }
    return 'iteration_limit';
  }

  const all = new Array(cols).fill(true);
  if (nArt) {
    const c1 = new Array(cols).fill(0);
    artCols.forEach(j => { c1[j] = 1; });
    run(c1, all);
    let infeas = 0;
    for (let i = 0; i < m; i++) if (c1[basis[i]]) infeas += T[i][cols];
    if (infeas > 1e-6 * Math.max(1, ...rows.map(r => Math.abs(r.b)))) return { status: 'infeasible' };
    // drive remaining artificials out of the basis
    for (let i = 0; i < m; i++) {
      if (!c1[basis[i]]) continue;
      for (let j = 0; j < n + nSlack; j++) if (Math.abs(T[i][j]) > EPS) { pivot(i, j); break; }
    }
  }
  const allowed = all.map((_, j) => j < n + nSlack);
  const c2 = new Array(cols).fill(0);
  for (let j = 0; j < n; j++) c2[j] = lp.c[j];
  const st = run(c2, allowed);
  if (st !== 'optimal') return { status: st };
  const x = new Array(n).fill(0);
  for (let i = 0; i < m; i++) if (basis[i] < n) x[basis[i]] = T[i][cols];
  return { status: 'optimal', x, value: x.reduce((acc, v, j) => acc + v * lp.c[j], 0) };
}
if (typeof module !== 'undefined') module.exports = { solveLP };
