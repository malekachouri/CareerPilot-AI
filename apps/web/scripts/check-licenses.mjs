// Fails if a production dependency has a licence outside the allow-list
// (docs/FREE_AND_OPEN_SOURCE_STACK.md §14). Usage: pnpm licenses list --prod --json | node scripts/check-licenses.mjs
import { readFileSync } from "node:fs";

const ALLOWED = /^(MIT|ISC|BSD-[23]-Clause|Apache-2\.0|0BSD|MPL-2\.0|CC0-1\.0|BlueOak-1\.0\.0|Unlicense|Python-2\.0|CC-BY-4\.0)$/;

// Reviewed exceptions: package name prefix -> reason.
const EXCEPTIONS = {
  "@img/sharp-libvips-": "LGPL-3.0 libvips, shipped unmodified and dynamically linked by sharp (Next.js image optimisation)",
};

const data = JSON.parse(readFileSync(0, "utf8"));
let failed = false;
for (const [license, packages] of Object.entries(data)) {
  const ok = license.split(/ OR | AND |[()]/).map((p) => p.trim()).filter(Boolean).every((p) => ALLOWED.test(p));
  if (ok) continue;
  for (const pkg of packages) {
    const exception = Object.keys(EXCEPTIONS).find((prefix) => pkg.name.startsWith(prefix));
    if (exception) {
      console.log(`exception: ${pkg.name} (${license}) — ${EXCEPTIONS[exception]}`);
    } else {
      console.error(`NOT ALLOWED: ${pkg.name} (${license})`);
      failed = true;
    }
  }
}
console.log(failed ? "licence check: FAILED" : "licence check: OK");
process.exit(failed ? 1 : 0);
