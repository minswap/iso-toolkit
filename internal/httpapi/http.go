package httpapi

import (
	"context"
	"crypto/tls"
	"fmt"
	"github.com/gorilla/mux"
	"github.com/urfave/negroni"
	"iso-toolkit/internal/logger"
	"log"
	"net/http"
	"runtime"
	"strings"
	"time"
)

type HTTPRoute interface {
	GetType() string
	Register(router *httpRouter, basePath string, mid []negroni.Handler)
}

type HTTPPrefixHandler struct {
	pathPrefix string
	handler    http.Handler
}

type httpRouter struct {
	base       *mux.Router
	timeout    time.Duration
	timeoutMsg string
}

type HTTPRouterOption func(router *httpRouter)

type HTTPServer struct {
	name              string
	address           string
	server            *http.Server
	handlers          []*HTTPPrefixHandler
	tlsConfig         *tls.Config
	readTimeout       time.Duration
	readHeaderTimeout time.Duration
	writeTimeout      time.Duration
	idleTimeout       time.Duration
}

type HTTPEndpointRoute struct {
	Name        string        `json:"name"`
	Method      string        `json:"method"`
	Pattern     string        `json:"pattern"`
	PathPrefix  bool          `json:"path_prefix"`
	Timeout     time.Duration `json:"timeout"`
	Handler     http.Handler  `json:"-"`
	HandlerName string        `json:"handler,omitempty"` // used for load from file only
}

type HTTPServerOption func(s *HTTPServer)

// HTTPHandlerFactory generator for generating a handler base on family name `fname` and list of arguments
type HTTPHandlerFactory func(fname string, args ...string) http.Handler

// HTTPMiddlewareFactory generator for generating a middleware base on family name `fname` and list of arguments
type HTTPMiddlewareFactory func(fname string, args ...string) negroni.Handler

func NewHTTPServer(options ...HTTPServerOption) *HTTPServer {
	server := &HTTPServer{}

	for _, option := range options {
		option(server)
	}

	if server.name == "" {
		log.Panic("must set name for HTTP server")
	}

	if server.readTimeout == 0 {
		server.readTimeout = defaultReadTimeout
	}
	if server.readHeaderTimeout == 0 {
		server.readHeaderTimeout = defaultReadHeaderTimeout
	}
	if server.writeTimeout == 0 {
		server.writeTimeout = defaultWriteTimeout
	}
	if server.idleTimeout == 0 {
		server.idleTimeout = defaultIdleTimeout
	}

	return server
}

// Run serve HTTP server
func (s *HTTPServer) Run() error {
	s.prepare()
	return s.start()
}

func (s *HTTPServer) prepare() {
	handler := negroni.New()
	router := mux.NewRouter()
	for _, prefixHandler := range s.handlers {
		router.PathPrefix(prefixHandler.pathPrefix).Handler(prefixHandler.handler)
	}

	handler.UseHandler(router)
	s.server = &http.Server{
		Addr:              s.address,
		Handler:           handler,
		TLSConfig:         s.tlsConfig,
		ReadTimeout:       s.readTimeout,
		ReadHeaderTimeout: s.readHeaderTimeout,
		WriteTimeout:      s.writeTimeout,
		IdleTimeout:       s.idleTimeout,
	}
}

// start run HTTP server on address, must call after prepare
func (s *HTTPServer) start() error {
	logger.Infof("HTTP %v listening on: %v", s.name, s.address)
	if s.tlsConfig != nil {
		// certificate must be configured in tlsConfig
		return s.server.ListenAndServeTLS("", "")
	}
	return s.server.ListenAndServe()
}

// Stop gracefully shutdown HTTP server
func (s *HTTPServer) Stop(ctx context.Context) {
	logger.Infof("HTTP %v shutting down...", s.name)
	if s.server != nil {
		err := s.server.Shutdown(ctx)
		if err != nil {
			log.Panic(err)
		}
	}
	logger.Infof("HTTP %v gracefully stopped", s.name)
}

// HTTPServerName set name of http server
func HTTPServerName(name string) HTTPServerOption {
	return func(s *HTTPServer) {
		s.name = name
	}
}

// HTTPServerAddress address of http server
func HTTPServerAddress(host string, port int) HTTPServerOption {
	return func(s *HTTPServer) {
		s.address = fmt.Sprintf("%s:%d", host, port)
	}
}

// HTTPServerHandler setup server handler
func HTTPServerHandler(router http.Handler, globalMiddlewareHandlers ...negroni.Handler) HTTPServerOption {
	return func(s *HTTPServer) {
		// init global middleware handlers for all request
		nHandler := negroni.New()
		for _, mid := range globalMiddlewareHandlers {
			nHandler.Use(mid)
		}

		// init gorilla mux router
		nHandler.UseHandler(router)

		// assign handler
		s.handlers = []*HTTPPrefixHandler{
			{
				pathPrefix: "/",
				handler:    nHandler,
			},
		}
	}
}

var namedHandlers = make(map[string]http.Handler)
var namedMiddlewares = make(map[string]negroni.Handler)
var namedHandlerFactories = make(map[string]HTTPHandlerFactory)
var namedMiddlewareFactories = make(map[string]HTTPMiddlewareFactory)

func NewHTTPRouter(routes []HTTPRoute, basePath string, opts ...HTTPRouterOption) *mux.Router {
	router := &httpRouter{
		base: mux.NewRouter().StrictSlash(true),
	}

	for _, opt := range opts {
		opt(router)
	}

	for _, route := range routes {
		route.Register(router, basePath, nil)
	}
	return router.base
}

func (r *HTTPEndpointRoute) GetType() string {
	return "endpoint"
}

func (r *HTTPEndpointRoute) Register(router *httpRouter, basePath string, mids []negroni.Handler) {
	if r.Handler == nil {
		if h, ok := namedHandlers[r.HandlerName]; ok {
			r.Handler = h
		} else {
			fName, args := getRouteFamilyName(r.HandlerName)
			if fHandler, ok := namedHandlerFactories[fName]; ok {
				r.Handler = fHandler(fName, args...)
			}
		}
	}
	if r.Handler == nil {
		log.Fatalf("missing handler of route %v", r.Name)
	}

	var handlers []negroni.Handler
	handlers = append(handlers, mids...)
	wrapHandler := r.Handler
	if r.Timeout == 0 {
		r.Timeout = router.timeout
	}
	if r.Timeout > 0 {
		msg := router.timeoutMsg
		if msg == "" {
			msg = "request timeout"
		}
		wrapHandler = newTimeoutHandler(wrapHandler, r.Timeout, msg)
	}
	handlers = append(handlers, negroni.Wrap(wrapHandler))
	if r.PathPrefix {
		router.base.PathPrefix(basePath + r.Pattern).
			Methods(r.Method).
			Handler(negroni.New(handlers...)).
			Name(r.Name)
	} else {
		router.base.
			Path(basePath + r.Pattern).
			Methods(r.Method).
			Handler(negroni.New(handlers...)).
			Name(r.Name)
	}
}

func getRouteFamilyName(name string) (string, []string) {
	parts := strings.Split(name, ":")
	if len(parts) < 2 {
		return name, nil
	}

	return parts[0], strings.Split(strings.Join(parts[1:], ":"), ";")
}

// newTimeoutHandler timeout handler with panic handler,
// workaround to resolve this issue: https://github.com/golang/go/issues/27375
func newTimeoutHandler(inner http.Handler, td time.Duration, msg string) http.Handler {
	return http.TimeoutHandler(&panicWrapHandler{inner: inner}, td, msg)
}

// HTTPMiddlewareRoute -- Defines a chain of middleware, e.g. a human readable name with inner endpoint routes
type HTTPMiddlewareRoute struct {
	Endpoints       []*HTTPEndpointRoute `json:"endpoints"`
	SubRoutes       []HTTPRoute          `json:"sub_routes"`
	Middleware      []negroni.Handler    `json:"-"`
	MiddlewareNames []string             `json:"middleware_names,omitempty"`
}

func (r *HTTPMiddlewareRoute) GetType() string {
	return "middleware"
}

func (r *HTTPMiddlewareRoute) Register(router *httpRouter, basePath string, baseMids []negroni.Handler) {
	mids := r.Middleware
	if len(mids) == 0 && len(r.MiddlewareNames) > 0 {
		// generate middleware from generator
		for _, named := range r.MiddlewareNames {
			if mid, ok := namedMiddlewares[named]; ok {
				mids = append(mids, mid)
				continue
			}
			fName, args := getRouteFamilyName(named)
			if fMid, ok := namedMiddlewareFactories[fName]; ok {
				mids = append(mids, fMid(fName, args...))
			}
		}
	}
	mids = append(baseMids, mids...)
	for _, subRoute := range r.Endpoints {
		subRoute.Register(router, basePath, mids)
	}
	for _, subRoute := range r.SubRoutes {
		subRoute.Register(router, basePath, mids)
	}
}

type panicWrapHandler struct {
	inner http.Handler
}

func (h *panicWrapHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	defer func() {
		if err := recover(); err != nil {
			if err != http.ErrAbortHandler {
				const size = 2 << 13
				buf := make([]byte, size)
				buf = buf[:runtime.Stack(buf, false)]
				logger.Errorf("PANIC: %s\n%s", err, buf)
			}
			panic(http.ErrAbortHandler)
		}
	}()
	h.inner.ServeHTTP(w, r)
}
