{
  description = "Locked, Nix-resolved Dhall imports";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        dhall-purifier = final.lib.makeScope final.newScope (scope: {
          tools = scope.callPackage ./pkgs/build-dhall-project/tools.nix { };
          nativeInspector = scope.callPackage ./pkgs/build-dhall-project/native.nix { };
          nativeFetch = scope.callPackage ./pkgs/build-dhall-project/fetch-import.nix { };
          sdkVersion = import ./pkgs/build-dhall-project/sdk-version.nix {
            nixpkgsSrc = nixpkgs;
            inherit (final) dhall;
          };
          cli = scope.callPackage ./pkgs/cli/default.nix {
            nixpkgsSrc = nixpkgs;
            purifierSrc = purifier;
          };
          buildDhallProject = scope.callPackage ./pkgs/build-dhall-project/default.nix {
            purifier = import (purifier + "/nix/lib") { inherit (final) lib; };
          };
        });
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).dhall-purifier.cli;
        cli = self.packages.${system}.default;
      });
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/dhall-purifier";
          meta.description = "Lock native Dhall imports";
        };
      });
      lib.dhall-purifier = (nixpkgs.lib.extend (import ./lib-overlays/default)).dhall-purifier;
      checks = forAll (
        system:
        let
          p = pkgsFor system;
          b = p.dhall-purifier.buildDhallProject {
            src = ./examples/minimal;
            exportJSON = true;
            doCheck = true;
            checkCommand = ''test "$(dhall-to-json --file "$out/source.dhall" | ${p.jq}/bin/jq .answer)" = 42'';
          };
        in
        {
          inherit (b.packages) environment project;
          release = b.release;
          json = import (purifier + "/tests/json-consumer.nix") {
            pkgs = p;
            producer = b;
            expectedKey = "answer";
            expectedValue = 42;
          };
          resources = import ./tests/resource-consumer.nix {
            pkgs = p;
            projection = b.projections.resources;
          };
          cli = self.packages.${system}.default;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
