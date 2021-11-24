package httpapi

import (
	"encoding/json"
	"net/http"
	"strconv"
)

func RespondJSON(w http.ResponseWriter, status int, payload interface{}) {
	data, err := json.Marshal(payload)
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte(err.Error()))
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Content-Length", strconv.Itoa(len(data)))
	w.WriteHeader(status)
	_, _ = w.Write(data)
}

func RespondBytes(w http.ResponseWriter, status int, bytes []byte) {
	w.Header().Set("Content-Type", "application/octet-stream")
	w.Header().Set("Content-Length", strconv.Itoa(len(bytes)))
	w.WriteHeader(status)
	_, _ = w.Write(bytes)
}

func RespondMessage(w http.ResponseWriter, status int, message string) {
	RespondJSON(w, status, struct {
		Message string `json:"message"`
	}{
		Message: message,
	})
}
