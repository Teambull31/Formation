environments = {
  dev     = { replicas = 1, debug = true }
  staging = { replicas = 2, debug = true }
  prod    = { replicas = 3, debug = false }
}
