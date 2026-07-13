use tauri::{
    api::process::CommandEvent,
    Manager,
};
use tauri_plugin_shell::ShellExt;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            // Start Python sidecar
            let shell = app.shell();
            let sidecar_command = shell.sidecar("sidecar")
                .expect("failed to create sidecar command");
            let (mut rx, _child) = sidecar_command
                .spawn()
                .expect("failed to spawn sidecar");

            // Spawn a task to monitor sidecar output
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            println!("[sidecar] {}", line);
                        }
                        CommandEvent::Stderr(line) => {
                            eprintln!("[sidecar:err] {}", line);
                        }
                        CommandEvent::Error(err) => {
                            eprintln!("[sidecar:error] {}", err);
                        }
                        CommandEvent::Terminated(status) => {
                            eprintln!("[sidecar] terminated with code {:?}", status.code);
                            break;
                        }
                        _ => {}
                    }
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // Hide instead of close (keep running in tray)
                window.hide().unwrap();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running application");
}
