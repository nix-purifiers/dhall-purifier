{ root, lockFile }:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  lib = pkgs.lib;
  purifier = import ((/. + "@purifier@") + "/nix/lib") { inherit lib; };
  tools = pkgs.callPackage ./tools.nix { };
  nativeFetch = pkgs.callPackage ./fetch-import.nix { inherit tools; };
  nativeInspector = pkgs.callPackage ./native.nix { };
  sdkVersion = import ./sdk-version.nix {
    inherit nixpkgsSrc;
    inherit (pkgs) dhall;
  };
  builder = pkgs.callPackage ./build-project.nix {
    inherit
      purifier
      nativeFetch
      nativeInspector
      tools
      sdkVersion
      ;
  };
in
(builder {
  src = /. + root;
  lockFile = /. + lockFile;
}).release
