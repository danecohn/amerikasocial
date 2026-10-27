# Current desktop download verification

The previous fallback catalogue could serve older branded installers after GitHub's anonymous API rate limit. Published release metadata is now refreshed for the verified VigilTech releases, using exact repository asset URLs and matching SHA-256 links. Existing download filenames remain available.

Social1.3.2, Game Producer0.1.6, Venture Zen1.23.4b-4, Mail1.0.7, Mind0.1.2, Prompter0.1.3 and Lookout0.1.2 are published. Journal1.0.3 and offline Office0.5.0 metadata must only be added after their release jobs publish successfully.

Journal uses the shared validated release reader through its existing endpoint/JSON shape. Its Linux DEBs and adjacent checksums are exposed alongside AppImages. Successful metadata is cached for ten minutes to reduce GitHub API traffic; newer cached releases cannot be replaced by an older fallback. Source and web bundles are not offered as native installers.

Small download labels are raised to readable sizes and narrow-screen controls retain44px minimum height. Supplied artwork and galleries remain unaltered. Native release checks run on their matching OS/CPU runners; ad-hoc Mac integrity verification does not constitute Apple notarization.
