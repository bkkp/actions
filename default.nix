{ pkgs ? import ./nix { } }:
{
  update-nix-sources = pkgs.callPackage ./actions/nix/update-nix-sources { };
}
