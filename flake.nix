{
  description = "AlgoMatter Development Environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            nodejs_20
            python3
            python3Packages.pip
            python3Packages.virtualenv
            # docker
            # docker-compose
            # postgresql_16
            # redis
          ];

          shellHook = ''
            echo "🌿 Welcome to the AlgoMatter Development Environment"
            echo "Node.js: $(node --version)"
            echo "Python: $(python --version)"
            echo "Docker: $(docker --version)"
          '';
        };
      }
    );
}
