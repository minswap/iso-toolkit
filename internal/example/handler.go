package example

import (
	"iso-toolkit/internal/httpapi"
	"net/http"
)

type Handler struct {
	service *Service
}

func NewHandler(service *Service) *Handler {
	return &Handler{service}
}

func (h *Handler) HandlerExample() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		httpapi.RespondMessage(w, http.StatusOK, "success")
	})
}
