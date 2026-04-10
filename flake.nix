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
            nginx
            python3
            python3Packages.pip
            python3Packages.virtualenv
            # docker
            # docker-compose
            # postgresql_16
            # redis
          ];

          shellHook = ''
            GITNEXUS_DIR="$PWD/.gitnexus-local"
            GITNEXUS_BIN="$GITNEXUS_DIR/node_modules/.bin"
            if [ ! -f "$GITNEXUS_BIN/gitnexus" ]; then
              echo "Installing gitnexus@1.5.3..."
              mkdir -p "$GITNEXUS_DIR"
              npm install --prefix "$GITNEXUS_DIR" gitnexus@1.5.3 --no-fund --no-audit --silent
            fi
            export PATH="$GITNEXUS_BIN:$PATH"
            echo "🌿 Welcome to the AlgoMatter Development Environment"
            echo "Node.js: $(node --version)"
            echo "Python: $(python --version)"
            echo "Docker: $(docker --version)"
            echo "Indexing codebase with GitNexus..."
            gitnexus analyze --silent 2>/dev/null || gitnexus analyze
          '';
        };
      }
    );
}
