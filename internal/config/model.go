package config

type Config struct {
	HTTP httpConfig
}

type httpConfig struct {
	Host string
	Port int
}
