package config

import (
	"github.com/spf13/viper"
	"log"
	"strings"
)

var global *Config

// New read config from config.yaml and env.
// If you want to override config.yaml key, replace '.' with '_' and uppercase(ex: http.host to HTTP_HOST).
func New() *Config {
	viper.SetConfigType("yaml")
	viper.AddConfigPath(".")
	viper.AutomaticEnv()
	viper.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	viper.SetConfigName("config")
	if err := viper.ReadInConfig(); err != nil {
		log.Fatalf("fail to read config: %v", err)
	}
	viper.SetConfigName("config.local")
	if err := viper.MergeInConfig(); err != nil {
		log.Printf("fail to read local config file: %v", err)
	}

	cfg := &Config{
		HTTP: httpConfig{
			Host: viper.GetString("http.host"),
			Port: viper.GetInt("http.port"),
		},
	}

	return cfg
}

func Init(c *Config) {
	global = c
}

func Get() *Config {
	return global
}
