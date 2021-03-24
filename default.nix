{ pkgs ? import ./nix { } }:
{
  update-nix-sources = pkgs.callPackage ./actions/nix/update-nix-sources { };
  deploy-to-bkknix = pkgs.callPackage ./actions/nix/deploy-to-bkknix { };
}
