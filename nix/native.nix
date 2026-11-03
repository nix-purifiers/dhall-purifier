{ runCommand, haskellPackages }:
let
  ghc = haskellPackages.ghcWithPackages (h: [
    h.dhall
    h.aeson
    h.prettyprinter
    h.transformers
  ]);
in
runCommand "dhall-native-inspector" { nativeBuildInputs = [ ghc ]; } ''
  mkdir -p "$out/bin"
  ghc -O1 ${../native/Inspect.hs} -outputdir build -o "$out/bin/dhall-inspect"
''
