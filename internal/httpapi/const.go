package httpapi

import "time"

const (
	defaultReadTimeout       = time.Second * 15
	defaultReadHeaderTimeout = time.Second * 15
	defaultWriteTimeout      = time.Second * 15
	defaultIdleTimeout       = time.Second * 60
)
