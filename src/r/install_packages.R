# Run once from the repo root:  source("src/r/install_packages.R")
pkgs <- c("DBI", "RPostgres", "dplyr", "dbplyr", "tidyr", "ggplot2", "arrow", "here", "knitr", "rmarkdown")
missing <- setdiff(pkgs, rownames(installed.packages()))
if (length(missing)) install.packages(missing)
