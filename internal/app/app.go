package app

import (
	"context"
	"iso-toolkit/internal/config"
	"iso-toolkit/internal/example"
	"iso-toolkit/internal/httpapi"
	"iso-toolkit/internal/httpapi/route"
	"iso-toolkit/internal/logger"
	"net/http"
)

type Closeable interface {
	Close() error
}

type App struct {
	server  *httpapi.HTTPServer
	closers []Closeable
}

// NewWithDefault Manual DI
func NewWithDefault() (*App, error) {
	globalConfig := config.Get()

	// Init services
	exampleService := example.NewService()

	// Init handler
	exampleHandler := example.NewHandler(exampleService)

	routes := route.NewRoutes(
		exampleHandler,
	)
	server := NewServer(globalConfig, routes)

	closers := []Closeable{}

	return New(server, closers), nil
}

func New(server *httpapi.HTTPServer, closers []Closeable) *App {
	return &App{server, closers}
}

// Start the app
func (s *App) Start(ctx context.Context) {
	// Start the HTTP HTTPServer in a way that we can gracefully shut it down again
	if err := s.server.Run(); err != http.ErrServerClosed {
		s.server.Stop(ctx)
	}
}

// Shutdown the app
func (s *App) Shutdown(ctx context.Context) {
	// Shutdown HTTP server
	s.server.Stop(ctx)

	// Close all dependencies connection
	for _, closer := range s.closers {
		if err := closer.Close(); err != nil {
			logger.Errorf("fail to close: %v", err)
		}
	}

	// Flush all buffers
	logger.Sync()
}
