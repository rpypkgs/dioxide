{
  description = "A MIDI synthesizer designed for M-Audio Oxygen controllers";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    flake-utils.url = "github:numtide/flake-utils";
    rpypkgs = {
      url = "github:rpypkgs/rpypkgs";
      # url = "/home/simpson/git/rpypkgs";
      inputs = {
        nixpkgs.follows = "nixpkgs";
        flake-utils.follows = "flake-utils";
      };
    };
  };

  outputs = { self, nixpkgs, flake-utils, rpypkgs }:
    flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = import nixpkgs { inherit system; };
      dioxide0 = pkgs.stdenv.mkDerivation {
        name = "dioxide";
        version = "0.1";
        nativeBuildInputs = with pkgs; [ autoreconfHook pkg-config ];
        buildInputs = with pkgs; [ alsaLib SDL ];
        src = ./.;
      };
      dioxide1 = rpypkgs.lib.${system}.mkRPythonDerivation {
        entrypoint = "dioxide.py";
        binName = "dioxide";
        optLevel = "2";
      } {
        pname = "dioxide";
        version = "1.1";

        src = ./.;

        buildInputs = with pkgs; [ jack2.dev ];
      };
      midisineSrc = pkgs.fetchurl {
        url = "https://github.com/jackaudio/example-clients/raw/refs/heads/master/midisine.c";
        sha256 = "0qn96gzrjfhbdr2lyldrp7ribxrlpjcqqnhjjrls9j68vjlnc3im";
      };
      midisine = pkgs.stdenv.mkDerivation {
        name = "midisine";
        version = "2022";
        nativeBuildInputs = with pkgs; [ pkg-config ];
        buildInputs = with pkgs; [ jack2.dev ];
        src = ./.;
        buildPhase = ''
          cp ${midisineSrc} midisine.c
          CFLAGS=$(pkg-config --cflags jack) LDFLAGS="-lm $(pkg-config --libs jack)" make midisine
        '';
        installPhase = ''
          mkdir -p $out/bin/
          cp midisine $out/bin/
        '';
      };
    in {
      packages = {
        inherit midisine;
        inherit dioxide0 dioxide1;
        default = dioxide1;
      };
      devShells.default = pkgs.mkShell {
        packages = with pkgs; [
          gdb linuxPackages.perf
        ];
      };
    });
}
