package main

import (
	"context"
	"iso-toolkit/internal/app"
	"iso-toolkit/internal/config"
	"iso-toolkit/internal/logger"
	"math/rand"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	// Seed randomizer
	rand.Seed(time.Now().UnixNano())

	// Initialize global objects
	config.Init(config.New())
	logger.Init(logger.New())

	app, err := app.NewWithDefault()
	if err != nil {
		logger.Fatalf("fail to init app: %v", err)
	}

	// Handle interrupt app
	c := make(chan os.Signal)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-c
		logger.Info("Shutdown app gracefully")
		app.Shutdown(context.Background())
		os.Exit(1)
	}()

	app.Start(context.Background())
}
