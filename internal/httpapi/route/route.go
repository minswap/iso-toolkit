package route

import (
	"iso-toolkit/internal/example"
	"iso-toolkit/internal/httpapi"
	"net/http"
)

func NewRoutes(example *example.Handler) []httpapi.HTTPRoute {
	routes := []httpapi.HTTPRoute{
		&httpapi.HTTPEndpointRoute{
			Name:    "Example handler",
			Method:  http.MethodGet,
			Pattern: "/example",
			Handler: example.HandlerExample(),
		},
	}

	return routes
}
