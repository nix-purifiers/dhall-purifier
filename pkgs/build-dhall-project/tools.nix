{ haskellPackages, haskell }:
let
  h = haskellPackages.override {
    overrides = self: super: { dhall = haskell.lib.disableCabalFlag super.dhall "with-http"; };
  };
in
{
  dhall = h.dhall;
  dhall-json = h.dhall-json;
  dhall-lsp-server = h.dhall-lsp-server;
}
