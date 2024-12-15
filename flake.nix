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
        withLibs = libs: [ libs.rsdl ];
      } {
        pname = "dioxide";
        version = "1.0";

        src = ./.;

        buildInputs = with pkgs; [ alsaLib SDL ];
      };
    in {
      packages = {
        default = dioxide0;
        dioxide = dioxide0;
        dioxide1 = dioxide1;
      };
      devShells.default = pkgs.mkShell {
        packages = with pkgs; [
          gdb linuxPackages.perf
        ];
      };
    });
}
