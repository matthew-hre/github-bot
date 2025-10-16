{
  description = "Github Discord Bot - Nix development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python313
            uv
            
            ruff
            just
            
            libsodium
            libffi
            openssl
          ];

          shellHook = ''
            echo "Python: $(python --version)"
            echo "uv: $(uv --version)"
            echo ""
            echo "Available commands:"
            echo "  uv run -m app          - Run the bot"
            echo "  just fix               - Run fixers (ruff, taplo)"
            echo "  just check             - Run all checks (ruff, type checking)"
            echo "  uv sync                - Install dependencies"
          '';
        };
      }
    );
}
