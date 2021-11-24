package logger

import (
	"go.uber.org/zap"
)

var global *Logger

type Logger struct {
	*zap.SugaredLogger
}

func New() *Logger {
	var zapLogger *zap.Logger
	// Always use development mode for easier debugging by eyes
	zapLogger, _ = zap.NewDevelopment()
	defer zapLogger.Sync()

	return &Logger{zapLogger.Sugar()}
}

func Init(c *Logger) {
	global = c
}

// Debug uses fmt.Sprint to construct and log a message.
func Debug(args ...interface{}) {
	global.Debug(args...)
}

// Debugw logs a message with some additional context.
func Debugw(msg string, keysAndValues ...interface{}) {
	global.Debugw(msg, keysAndValues...)
}

// Debugf uses fmt.Sprintf to log a templated message.
func Debugf(template string, args ...interface{}) {
	global.Debugf(template, args...)
}

// Info uses fmt.Sprint to construct and log a message.
func Info(args ...interface{}) {
	global.Info(args...)
}

// Infow logs a message with some additional context.
func Infow(msg string, keysAndValues ...interface{}) {
	global.Infow(msg, keysAndValues...)
}

// Infof uses fmt.Sprintf to log a templated message.
func Infof(template string, args ...interface{}) {
	global.Infof(template, args...)
}

// Error uses fmt.Sprint to construct and log a message.
func Error(args ...interface{}) {
	global.Error(args...)
}

// Errorw logs a message with some additional context.
func Errorw(msg string, keysAndValues ...interface{}) {
	global.Errorw(msg, keysAndValues...)
}

// Errorf uses fmt.Sprintf to log a templated message.
func Errorf(template string, args ...interface{}) {
	global.Errorf(template, args...)
}

// Fatal uses fmt.Sprint to construct and log a message, then calls os.Exit.
func Fatal(args ...interface{}) {
	global.Fatal(args...)
}

// Fatalf uses fmt.Sprintf to log a templated message, then calls os.Exit.
func Fatalf(template string, args ...interface{}) {
	global.Fatalf(template, args...)
}

// Fatalw logs a message with some additional context, then calls os.Exit. The
func Fatalw(msg string, keysAndValues ...interface{}) {
	global.Fatalw(msg, keysAndValues...)
}

// Panic uses fmt.Sprint to construct and log a message, then panics.
func Panic(args ...interface{}) {
	global.Panic(args...)
}

// Sync flushes any buffered log entries.
func Sync() error {
	return global.Sync()
}
