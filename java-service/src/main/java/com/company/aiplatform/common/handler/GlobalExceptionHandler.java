package com.company.aiplatform.common.handler;

import com.company.aiplatform.common.enums.ResultCode;
import com.company.aiplatform.common.exception.BusinessException;
import com.company.aiplatform.common.result.Result;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.async.AsyncRequestTimeoutException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.NoHandlerFoundException;

import java.util.StringJoiner;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    // === 业务异常 ===
    @ExceptionHandler(BusinessException.class)
    public Result<Void> handleBusinessException(BusinessException e) {
        log.warn("业务异常: code={}, message={}", e.getCode(), e.getMessage());
        return Result.fail(e.getCode(), e.getMessage());
    }

    // === 参数校验异常 (@Valid) ===
    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleMethodArgumentNotValid(MethodArgumentNotValidException e) {
        StringJoiner sj = new StringJoiner("; ");
        for (FieldError fe : e.getBindingResult().getFieldErrors()) {
            sj.add(fe.getField() + ": " + fe.getDefaultMessage());
        }
        return Result.fail(ResultCode.BAD_REQUEST, sj.toString());
    }

    // === 参数绑定异常 ===
    @ExceptionHandler(BindException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleBindException(BindException e) {
        StringJoiner sj = new StringJoiner("; ");
        for (FieldError fe : e.getFieldErrors()) {
            sj.add(fe.getField() + ": " + fe.getDefaultMessage());
        }
        return Result.fail(ResultCode.BAD_REQUEST, sj.toString());
    }

    // === 约束违反异常 (@Validated) ===
    @ExceptionHandler(ConstraintViolationException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleConstraintViolation(ConstraintViolationException e) {
        StringJoiner sj = new StringJoiner("; ");
        for (ConstraintViolation<?> cv : e.getConstraintViolations()) {
            sj.add(cv.getPropertyPath() + ": " + cv.getMessage());
        }
        return Result.fail(ResultCode.BAD_REQUEST, sj.toString());
    }

    // === 缺少请求参数 ===
    @ExceptionHandler(MissingServletRequestParameterException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleMissingParam(MissingServletRequestParameterException e) {
        return Result.fail(ResultCode.BAD_REQUEST, "缺少参数: " + e.getParameterName());
    }

    // === 参数类型不匹配 ===
    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleTypeMismatch(MethodArgumentTypeMismatchException e) {
        return Result.fail(ResultCode.BAD_REQUEST, "参数类型错误: " + e.getName());
    }

    // === 请求体格式错误 ===
    @ExceptionHandler(HttpMessageNotReadableException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleMessageNotReadable(HttpMessageNotReadableException e) {
        return Result.fail(ResultCode.BAD_REQUEST, "请求体格式错误");
    }

    // === HTTP方法不支持 ===
    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    @ResponseStatus(HttpStatus.METHOD_NOT_ALLOWED)
    public Result<Void> handleMethodNotSupported(HttpRequestMethodNotSupportedException e) {
        return Result.fail(ResultCode.BAD_REQUEST, "不支持的请求方法: " + e.getMethod());
    }

    // === 404 ===
    @ExceptionHandler(NoHandlerFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public Result<Void> handleNotFound(NoHandlerFoundException e) {
        return Result.fail(ResultCode.NOT_FOUND);
    }

    // === 异步请求超时 ===
    @ExceptionHandler(AsyncRequestTimeoutException.class)
    @ResponseStatus(HttpStatus.GATEWAY_TIMEOUT)
    public Result<Void> handleAsyncTimeout(AsyncRequestTimeoutException e) {
        log.warn("异步请求超时: {}", e.getMessage());
        return Result.fail(ResultCode.INTERNAL_ERROR, "请求处理超时，请稍后重试");
    }
    
    // === 兜底：未知异常 ===
    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public Result<Void> handleUnknownException(Exception e) {
        log.error("未知异常", e);
        return Result.fail(ResultCode.INTERNAL_ERROR);
    }
}
