using System;
using System.Runtime.InteropServices.JavaScript;
using Microsoft.JSInterop;
using System.Threading.Tasks;

namespace TimelineZLA.Pages
{
    public partial class Index : IDisposable
    {
        private int activeScene = 1;
        private bool isUploading = false;
        private int uploadProgress = 0;
        private bool isAttacked = false;
        private string pourState = "None"; // None, SaaS, ZLA, Complete
        private bool jigDissolved = false;
        private bool celebrateActive = false;

        [JSImport("triggerConfetti", "zla-interop")]
        internal static partial void TriggerConfettiJS();

        private async Task SimulateUpload()
        {
            if (isUploading) return;
            isUploading = true;
            uploadProgress = 0;
            StateHasChanged();
            
            while (uploadProgress < 100)
            {
                await Task.Delay(200);
                uploadProgress += 10;
                StateHasChanged();
            }
            isUploading = false;
            isAttacked = true;
            StateHasChanged();
        }

        private void NextScene()
        {
            if (activeScene < 5)
            {
                activeScene++;
                StateHasChanged();
            }
        }

        private void SetPourState(string state)
        {
            pourState = state;
            if (state == "ZLA")
            {
                jigDissolved = true;
            }
            StateHasChanged();
        }

        private void Celebrate()
        {
            celebrateActive = true;
            try
            {
                TriggerConfettiJS();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Confetti Trigger Error: {ex.Message}");
            }
            StateHasChanged();
        }

        public void Dispose()
        {
            // Clean up resources if necessary
        }
    }
}

