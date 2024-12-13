{
  description = "A music synthesizer";

  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = import nixpkgs { inherit system; };
      dioxide = pkgs.stdenv.mkDerivation {
        name = "dioxide";
        version = "0.1";
        nativeBuildInputs = with pkgs; [ autoreconfHook pkg-config ];
        buildInputs = with pkgs; [ alsaLib SDL ];
        src = ./.;
      };
    in {
      packages.default = dioxide;
    });
}
