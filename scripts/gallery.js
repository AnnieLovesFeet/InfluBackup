class LightboxCloseButton {
	constructor(onClose) {
		this.onClose = onClose;
	}

	render() {
		const button = document.createElement('button');
		button.className = 'lightbox-close';
		button.type = 'button';
		button.setAttribute('aria-label', 'Close');
		button.innerHTML = '&times;';
		button.addEventListener('click', this.onClose);
		return button;
	}
}

class Gallery {
	constructor(images = [], code = '') {
		this.images = images;
		this.code = code;
		this.currentIndex = 0;
		this.lightbox = null;
	}

	escapeHtml(value) {
		return String(value).replace(/[&<>"']/g, (character) => ({
			'&': '&amp;',
			'<': '&lt;',
			'>': '&gt;',
			'"': '&quot;',
			"'": '&#039;'
		}[character]));
	}

	render(container = document.querySelector('#gallery')) {
		if (!container) {
			throw new Error('Nie znaleziono elementu #gallery.');
		}

		container.className = 'gallery';

		if (!this.images.length) {
			container.innerHTML = '<p class="gallery-empty">Brak zdjęć w galerii.</p>';
			return container;
		}

		const images = this.images.map((imagePath, index) => {
			const imageUrl = this.getImageUrl(imagePath);
			const alt = `${this.code} - image ${index + 1}`;

			return `
				<figure class="gallery-item" data-index="${index}">
					<button class="gallery-image-button" type="button" aria-label="Open image ${index + 1}">
						<img src="${this.escapeHtml(imageUrl)}" alt="${this.escapeHtml(alt)}" loading="lazy">
					</button>
				</figure>
			`;
		}).join('');

		container.innerHTML = `
			<div class="gallery-grid">${images}</div>
		`;

		container.querySelectorAll('.gallery-item').forEach((item) => {
			item.querySelector('button').addEventListener('click', () => {
				this.openLightbox(Number(item.dataset.index));
			});
		});

		return container;
	}

	getImageUrl(imagePath) {
		return new URL(imagePath, `${window.location.origin}/`).href;
	}

	openLightbox(index) {
		this.currentIndex = index;
		this.lightbox = document.createElement('div');
		this.lightbox.className = 'lightbox';
		this.lightbox.innerHTML = `
			<div class="lightbox-content" role="dialog" aria-modal="true" aria-label="Image preview">
				<button class="lightbox-previous" type="button" aria-label="Previous image">&#10094;</button>
				<img class="lightbox-image" alt="">
				<button class="lightbox-next" type="button" aria-label="Next image">&#10095;</button>
			</div>
		`;

		document.body.append(this.lightbox);
		document.body.classList.add('lightbox-open');

		const lightboxContent = this.lightbox.querySelector('.lightbox-content');
		lightboxContent.prepend(new LightboxCloseButton(() => this.closeLightbox()).render());
		this.lightbox.querySelector('.lightbox-previous').addEventListener('click', () => this.showPrevious());
		this.lightbox.querySelector('.lightbox-next').addEventListener('click', () => this.showNext());
		this.lightbox.addEventListener('click', (event) => {
			if (event.target === this.lightbox) {
				this.closeLightbox();
			}
		});
		document.addEventListener('keydown', this.handleKeydown);

		this.updateLightbox();
	}

	updateLightbox() {
		const imagePath = this.images[this.currentIndex];
		const image = this.lightbox.querySelector('.lightbox-image');
		image.src = this.getImageUrl(imagePath);
		image.alt = `${this.code} - image ${this.currentIndex + 1}`;
	}

	showPrevious() {
		this.currentIndex = (this.currentIndex - 1 + this.images.length) % this.images.length;
		this.updateLightbox();
	}

	showNext() {
		this.currentIndex = (this.currentIndex + 1) % this.images.length;
		this.updateLightbox();
	}

	handleKeydown = (event) => {
		if (!this.lightbox) {
			return;
		}

		if (event.key === 'Escape') {
			this.closeLightbox();
		} else if (event.key === 'ArrowLeft') {
			this.showPrevious();
		} else if (event.key === 'ArrowRight') {
			this.showNext();
		}
	};

	closeLightbox() {
		if (!this.lightbox) {
			return;
		}

		this.lightbox.remove();
		this.lightbox = null;
		document.body.classList.remove('lightbox-open');
		document.removeEventListener('keydown', this.handleKeydown);
	}
}

async function renderGallery(group, code, jsonPath = '../../influencers.json') {
	const container = document.querySelector('#gallery');

	try {
		const response = await fetch(jsonPath);
		if (!response.ok) {
			throw new Error(`Nie udało się wczytać galerii: ${response.status}`);
		}

		const influencers = await response.json();
		const influencer = influencers.find((item) => (
			item.code === code && item.group === group
		));

		if (!influencer) {
			throw new Error(`Nie znaleziono galerii: ${group}/${code}`);
		}

		new Gallery(influencer.images || [], code).render(container);
	} catch (error) {
		if (container) {
			container.textContent = error.message;
		}
	}
}
