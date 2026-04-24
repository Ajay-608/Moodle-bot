from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def learning_dashboard(request):
    return render(request, 'learning/dashboard.html')

@login_required
def progress_tracker(request):
    return render(request, 'learning/progress.html')

@login_required
def learning_resources(request):
    return render(request, 'learning/resources.html')
