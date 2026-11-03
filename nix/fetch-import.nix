{
  lib,
  runCommand,
  writeText,
  dhall,
  tools,
  cacert,
}:
entry:
let
  expression = writeText "dhall-import.dhall" entry.dhall.expression;
in
runCommand (baseNameOf entry.path)
  {
    outputHashAlgo = null;
    outputHashMode = "flat";
    outputHash = entry.hash;
    nativeBuildInputs = [ cacert ];
    impureEnvVars = lib.fetchers.proxyImpureEnvVars;
  }
  ''
    set -euo pipefail
    ${lib.getExe dhall} --alpha --plain --file ${expression} | ${lib.getExe tools.dhall} encode > "$out"
  ''
