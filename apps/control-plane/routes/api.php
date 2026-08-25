<?php

declare(strict_types=1);

use App\Http\Controllers\Api\V1\ControlPlaneController;
use Illuminate\Support\Facades\Route;

Route::prefix('v1')->middleware('auth:sanctum')->group(function (): void {
    Route::middleware('abilities:control-plane:read')->group(function (): void {
        Route::get('/me', [ControlPlaneController::class, 'me']);
        Route::get('/tenants/current', [ControlPlaneController::class, 'currentTenant']);
        Route::get('/scenarios', [ControlPlaneController::class, 'scenarios']);
        Route::get('/scenarios/{scenarioId}', [ControlPlaneController::class, 'scenario']);
        Route::get('/assignments', [ControlPlaneController::class, 'assignments']);
    });

    Route::post('/simulation-start-requests', [ControlPlaneController::class, 'requestSimulationStart'])
        ->middleware('abilities:control-plane:simulation-start');
});
