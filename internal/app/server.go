package app

import (
	"github.com/rs/cors"
	"github.com/urfave/negroni"
	"iso-toolkit/internal/config"
	"iso-toolkit/internal/httpapi"
	"net/http"
)

func NewServer(config *config.Config, routes []httpapi.HTTPRoute) *httpapi.HTTPServer {
	recoveryMiddleware := negroni.NewRecovery()
	corsMiddleware := cors.New(cors.Options{
		AllowedOrigins: []string{"*"},
		AllowedMethods: []string{
			http.MethodHead,
			http.MethodGet,
			http.MethodPost,
			http.MethodDelete,
		},
	})

	return httpapi.NewHTTPServer(
		httpapi.HTTPServerName("iso-toolkit"),
		httpapi.HTTPServerAddress(config.HTTP.Host, config.HTTP.Port),
		httpapi.HTTPServerHandler(
			httpapi.NewHTTPRouter(routes, ""),
			recoveryMiddleware,
			corsMiddleware,
		),
	)
}
