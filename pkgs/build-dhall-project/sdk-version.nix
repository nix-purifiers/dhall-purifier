{ nixpkgsSrc, dhall }:
builtins.hashString "sha256" (
  builtins.toJSON {
    nixpkgs = toString nixpkgsSrc;
    version = dhall.version;
    inspector = builtins.hashFile "sha256" ../../native/Inspect.hs;
    tools = builtins.hashFile "sha256" ./tools.nix;
  }
)
